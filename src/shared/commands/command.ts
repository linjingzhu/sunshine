export const commandIds=["app.getVersion","browser.getState","browser.navigate","browser.back","browser.forward","browser.reload","browser.stop"] as const;
export type CommandId=(typeof commandIds)[number];
export interface BrowserSnapshot{url:string;title:string;isLoading:boolean;canGoBack:boolean;canGoForward:boolean;error?:string}
export type CommandRequest={id:"app.getVersion"}|{id:"browser.navigate";input:string}|{id:Exclude<CommandId,"app.getVersion"|"browser.navigate">};
export type CommandResult={ok:true;value?:string;browser?:BrowserSnapshot}|{ok:false;error:{code:string;message:string}};
export function isCommandRequest(value:unknown):value is CommandRequest{if(!value||typeof value!=="object")return false;const candidate=value as Record<string,unknown>;if(!commandIds.includes(candidate.id as CommandId))return false;return candidate.id!=="browser.navigate"||typeof candidate.input==="string"}
