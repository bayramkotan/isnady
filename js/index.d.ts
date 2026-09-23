export declare const version: string;
export declare const name: string;

export interface IsnadyInfo {
  name: string;
  version: string;
  dataLoaded: boolean;
  homepage: string;
}

export declare function info(): IsnadyInfo;
