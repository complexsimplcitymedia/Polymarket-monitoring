import asyncio
import json
import logging
import math
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    from polymarket_us import PolymarketUS
except ImportError:
    PolymarketUS = None

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import (
    ApiCreds,
    OrderArgs,
    OrderType,
    BalanceAllowanceParams,
    AssetType,
    OpenOrderParams,
)
from py_builder_signing_sdk.config import BuilderConfig
from py_builder_signing_sdk.signer import BuilderApiKeyCreds
from src.backend.config import settings

logger = logging.getLogger(__name__)


class PolymarketTradingService:
    """Service for interacting directly with Polymarket CLOB."""

    def __init__(self):
        self._client: Optional[ClobClient] = None
        self._cached_address: Optional[str] = None

    def get_us_client(self) -> Optional[Any]:
        """Get or initialize PolymarketUS client."""
        if not PolymarketUS:
            return None
        key_id = settings.POLYMARKET_KEY_ID or settings.POLYMARKET_API_KEY
        secret_key = settings.POLYMARKET_SECRET_KEY or settings.POLYMARKET_SECRET
        if key_id and secret_key:
            try:
                return PolymarketUS(
                    key_id=key_id,
                    secret_key=secret_key,
                )
            except Exception as e:
                logger.error(f"Failed to init PolymarketUS client: {e}")
        return None

    def get_client(self, override_key: Optional[str] = None) -> Optional[ClobClient]:
        """
        Get or initialize the ClobClient with signing credentials.
        """
        private_key = override_key or settings.POLYMARKET_PRIVATE_KEY
        if not private_key:
            return None

        # Re-initialize if key changed or not initialized
        if self._client is None or override_key:
            try:
                creds = None
                builder_cfg = None
                if settings.POLYMARKET_API_KEY and settings.POLYMARKET_SECRET and settings.POLYMARKET_PASSPHRASE:
                    creds = ApiCreds(
                        api_key=settings.POLYMARKET_API_KEY,
                        api_secret=settings.POLYMARKET_SECRET,
                        api_passphrase=settings.POLYMARKET_PASSPHRASE,
                    )
                    try:
                        builder_creds = BuilderApiKeyCreds(
                            key=settings.POLYMARKET_API_KEY,
                            secret=settings.POLYMARKET_SECRET,
                            passphrase=settings.POLYMARKET_PASSPHRASE,
                        )
                        builder_cfg = BuilderConfig(local_builder_creds=builder_creds)
                    except Exception as b_err:
                        logger.warning(f"Could not init BuilderConfig: {b_err}")

                client = ClobClient(
                    host=settings.POLYMARKET_HOST,
                    chain_id=settings.POLYMARKET_CHAIN_ID,
                    key=private_key,
                    creds=creds,
                    signature_type=settings.POLYMARKET_SIGNATURE_TYPE,
                    funder=settings.POLYMARKET_FUNDER or None,
                    builder_config=builder_cfg,
                )

                if not creds:
                    try:
                        derived_creds = client.create_or_derive_api_creds()
                        client.set_api_creds(derived_creds)
                    except Exception as e:
                        logger.warning(f"Could not auto-derive API creds: {e}")

                self._client = client
            except Exception as e:
                logger.error(f"Failed to initialize ClobClient: {e}")
                return None

        return self._client

    async def get_trading_status(self, private_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Check trading pipeline status, active wallet address, and USDC collateral/allowance.
        Supports both PolymarketUS API client and Polygon CLOB client.
        """
        # 1. First check PolymarketUS Client (Ed25519)
        us_client = self.get_us_client()
        if us_client:
            try:
                bal_resp = us_client.account.balances()
                balances = bal_resp.get("balances", []) if isinstance(bal_resp, dict) else []
                total_buying_power = 0.0
                total_balance = 0.0
                for b in balances:
                    total_buying_power += float(b.get("buyingPower", 0))
                    total_balance += float(b.get("currentBalance", 0))

                return {
                    "status": "READY",
                    "mode": "POLYMARKET_US_ED25519",
                    "message": "Polymarket US authenticated via Ed25519 key.",
                    "wallet_address": f"Polymarket-US ({settings.POLYMARKET_API_KEY[:8]}...)",
                    "funder_address": None,
                    "signature_type": "Ed25519",
                    "balance_usdc": round(total_buying_power, 2),
                    "allowance_usdc": round(total_balance, 2),
                    "can_trade": total_buying_power > 0 or total_balance > 0,
                }
            except Exception as e:
                logger.warning(f"PolymarketUS balance check error: {e}")

        # 2. Fall back to Polygon CLOB client
        client = self.get_client(private_key)
        if not client:
            return {
                "status": "UNCONFIGURED",
                "message": "Polymarket API credentials not configured.",
                "wallet_address": None,
                "balance_usdc": 0.0,
                "allowance_usdc": 0.0,
                "can_trade": False,
            }

        try:
            address = client.get_address()
            params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            balance_info = client.get_balance_allowance(params)
            
            raw_balance = float(balance_info.get("balance", 0))
            raw_allowance = float(balance_info.get("allowance", 0))

            balance_usdc = raw_balance / 1e6
            allowance_usdc = raw_allowance / 1e6

            return {
                "status": "READY",
                "mode": "POLYGON_CLOB",
                "message": "CLOB Trading Pipeline connected and authenticated.",
                "wallet_address": address,
                "funder_address": settings.POLYMARKET_FUNDER or address,
                "signature_type": str(settings.POLYMARKET_SIGNATURE_TYPE),
                "balance_usdc": round(balance_usdc, 2),
                "allowance_usdc": round(allowance_usdc, 2),
                "can_trade": balance_usdc > 0,
            }
        except Exception as e:
            logger.error(f"Error checking CLOB trading status: {e}")
            return {
                "status": "ERROR",
                "message": f"Failed to authenticate with CLOB: {str(e)}",
                "wallet_address": getattr(client, "get_address", lambda: None)(),
                "balance_usdc": 0.0,
                "allowance_usdc": 0.0,
                "can_trade": False,
            }

    async def get_order_book(self, token_id: str) -> Dict[str, Any]:
        """
        Get live order book for a specific token directly from CLOB.
        """
        try:
            client = self.get_client()
            if client:
                ob = client.get_order_book(token_id)
            else:
                # Public read using ephemeral unauthenticated client
                anon_client = ClobClient(host=settings.POLYMARKET_HOST)
                ob = anon_client.get_order_book(token_id)

            bids = getattr(ob, "bids", []) or []
            asks = getattr(ob, "asks", []) or []

            # Format bids/asks to dicts if needed
            formatted_bids = [{"price": float(b.price), "size": float(b.size)} for b in bids]
            formatted_asks = [{"price": float(a.price), "size": float(a.size)} for a in asks]

            best_bid = max([b["price"] for b in formatted_bids], default=0.0)
            best_ask = min([a["price"] for a in formatted_asks], default=1.0)
            spread = round(best_ask - best_bid, 4) if best_ask > best_bid else 0.0
            midpoint = round((best_bid + best_ask) / 2, 4) if (best_bid and best_ask) else 0.0

            return {
                "token_id": token_id,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "midpoint": midpoint,
                "spread": spread,
                "bids": formatted_bids[:10],
                "asks": formatted_asks[:10],
            }
        except Exception as e:
            logger.error(f"Error fetching order book for {token_id}: {e}")
            return {
                "token_id": token_id,
                "error": str(e),
                "best_bid": 0.0,
                "best_ask": 1.0,
                "spread": 1.0,
                "bids": [],
                "asks": [],
            }

    async def place_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str = "BUY",
        order_type: str = "GTC",
        private_key: Optional[str] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Place a limit order directly on Polymarket CLOB.
        
        Args:
            token_id: The outcome asset ID (YES or NO token).
            price: Price per share (between 0.01 and 0.99).
            size: Number of shares to buy/sell.
            side: "BUY" or "SELL".
            order_type: "GTC", "FOK", "FAK", or "GTD".
            private_key: Optional key override.
            dry_run: If True, validate order without submitting to chain.
        """
        side_upper = side.upper()
        if side_upper not in ("BUY", "SELL"):
            raise ValueError("Side must be BUY or SELL")

        if not (0.001 <= price <= 0.999):
            raise ValueError("Price must be between 0.001 and 0.999")

        if size <= 0:
            raise ValueError("Size must be greater than 0")

        total_value = round(price * size, 2)

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "order_id": "simulated_order_" + token_id[:8],
                "token_id": token_id,
                "side": side_upper,
                "price": price,
                "size": size,
                "total_cost_usdc": total_value,
                "message": "Order simulated successfully (dry run).",
            }

        client = self.get_client(private_key)
        if not client:
            raise ValueError("Polymarket trading wallet is not configured. Supply private key.")

        try:
            ot = getattr(OrderType, order_type.upper(), OrderType.GTC)
            order_args = OrderArgs(
                token_id=token_id,
                price=round(price, 3),
                size=round(size, 2),
                side=side_upper,
            )

            response = client.create_and_post_order(order_args)
            logger.info(f"CLOB Order placed: {response}")

            return {
                "success": True,
                "dry_run": False,
                "response": response,
                "order_id": response.get("orderID") or response.get("id"),
                "token_id": token_id,
                "side": side_upper,
                "price": price,
                "size": size,
                "total_cost_usdc": total_value,
            }
        except Exception as e:
            logger.error(f"CLOB Order placement failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "token_id": token_id,
                "side": side_upper,
                "price": price,
                "size": size,
            }

    async def place_parlay_bundle(
        self,
        legs: List[Dict[str, Any]],
        total_budget: float,
        allocation: str = "EQUAL",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute multiple legs of a synthetic parlay sequentially across CLOB order books.
        
        Args:
            legs: List of legs: [{"token_id": str, "side": "BUY", "price": float, "market_title": str}]
            total_budget: Total USDC budget for the parlay.
            allocation: "EQUAL" allocates budget equally across legs.
            dry_run: If True, simulates execution without posting to CLOB.
        """
        if not legs:
            raise ValueError("Parlay requires at least 2 legs")

        num_legs = len(legs)
        budget_per_leg = total_budget / num_legs

        results = []
        total_spent = 0.0
        all_success = True

        for idx, leg in enumerate(legs):
            token_id = leg["token_id"]
            price = float(leg.get("price", 0.50))
            side = leg.get("side", "BUY")
            size = round(budget_per_leg / price, 2) if price > 0 else 0

            logger.info(f"Executing Leg {idx+1}/{num_legs}: {leg.get('market_title', token_id)} - {size} shares @ {price}")

            order_res = await self.place_order(
                token_id=token_id,
                price=price,
                size=size,
                side=side,
                dry_run=dry_run,
            )

            results.append({
                "leg_index": idx + 1,
                "market_title": leg.get("market_title", "Unknown"),
                "token_id": token_id,
                "side": side,
                "price": price,
                "size": size,
                "cost_usdc": round(price * size, 2),
                "status": "SUCCESS" if order_res.get("success") else "FAILED",
                "details": order_res,
            })

            if order_res.get("success"):
                total_spent += round(price * size, 2)
            else:
                all_success = False

        return {
            "success": all_success,
            "dry_run": dry_run,
            "legs_count": num_legs,
            "total_budget": total_budget,
            "total_executed_usdc": round(total_spent, 2),
            "legs": results,
        }

    async def get_open_orders(self, market_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch open orders from the CLOB."""
        client = self.get_client()
        if not client:
            return []

        try:
            params = OpenOrderParams(market=market_id) if market_id else OpenOrderParams()
            orders = client.get_orders(params)
            return orders if isinstance(orders, list) else [orders]
        except Exception as e:
            logger.error(f"Error fetching open orders: {e}")
            return []

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel a specific order by ID."""
        client = self.get_client()
        if not client:
            raise ValueError("Trading client not configured.")

        try:
            res = client.cancel(order_id)
            return {"success": True, "cancelled_order_id": order_id, "response": res}
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return {"success": False, "error": str(e), "order_id": order_id}

    async def cancel_all_orders(self) -> Dict[str, Any]:
        """Cancel all open orders."""
        client = self.get_client()
        if not client:
            raise ValueError("Trading client not configured.")

        try:
            res = client.cancel_all()
            return {"success": True, "response": res}
        except Exception as e:
            logger.error(f"Failed to cancel all orders: {e}")
            return {"success": False, "error": str(e)}


trading_service = PolymarketTradingService()
