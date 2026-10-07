export const SPORT_CODES = ['nfl', 'mlb', 'nba', 'cfb', 'all'] as const;

export type SportCode = (typeof SPORT_CODES)[number];
export type MatchState = 'live' | 'upcoming' | 'finished';

export interface Team {
    id: string;
    name: string;
    shortName: string;
    badgeColor: string;
    logoUrl?: string;
    record?: string;
}

export interface ScoreSegment {
    label: string;
    home: string | number;
    away: string | number;
    active?: boolean;
}

export interface MatchEvent {
    id: string;
    minute?: string;
    kind: 'score' | 'turnover' | 'penalty' | 'period' | 'injury';
    team: 'home' | 'away';
    title: string;
    detail?: string;
}

export interface BaseballSituation {
    balls: number;
    strikes: number;
    outs: number;
    runnerOnFirst: boolean;
    runnerOnSecond: boolean;
    runnerOnThird: boolean;
    currentPitcher?: {
        name: string;
        hand: 'R' | 'L';
        pitchCount: number;
        era: string;
        strikeouts?: number;
    };
    currentBatter?: {
        name: string;
        avg: string;
        hits?: number;
        atBats?: number;
    };
}

export interface FootballSituation {
    down: number;
    distance: number;
    yardLine: string;
    possession: 'home' | 'away';
    redZone?: boolean;
}

export interface BasketballSituation {
    shotClock?: number;
    possession?: 'home' | 'away';
}

export type FeedProviderId = 'mlb_statsapi' | 'espn_fast' | 'poly_radar' | 'thescore_wire';

export interface FeedProviderConfig {
    id: FeedProviderId;
    name: string;
    short: string;
    latencyMs: number;
    status: 'optimal' | 'backup' | 'delayed';
    description: string;
}

export interface SportsMatch {
    id: string;
    sport: SportCode;
    leagueId: string;
    leagueName: string;
    status: MatchState;
    statusDetail: string;
    startTime: string;
    homeTeam: Team;
    awayTeam: Team;
    score: {
        home: number;
        away: number;
    };
    scoreSegments: ScoreSegment[];
    events?: MatchEvent[];
    venue?: string;
    marketId?: string;
    marketSlug?: string;
    marketTitle?: string;
    impliedOdds?: {
        home: number;
        away: number;
    };
    baseballSituation?: BaseballSituation;
    footballSituation?: FootballSituation;
    basketballSituation?: BasketballSituation;
}
