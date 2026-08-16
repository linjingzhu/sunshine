import{BrowserWindow,WebContentsView,type Rectangle}from"electron";
import type{BrowserSnapshot}from"../../shared/commands/command";
import{ipcChannels}from"../../shared/contracts/channels";
import{classifyNavigationInput}from"../navigation/classify-input";
const CHROME_HEIGHT=116;const HOME_URL="https://www.google.com/";
export class BrowserSurface{private readonly view:WebContentsView;private lastError:string|undefined;
constructor(private readonly window:BrowserWindow){this.view=new WebContentsView({webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,allowRunningInsecureContent:false}});window.contentView.addChildView(this.view);this.layout(window.getContentBounds());window.on("resize",()=>this.layout(window.getContentBounds()));window.on("closed",()=>{if(!this.view.webContents.isDestroyed())this.view.webContents.close()});this.view.webContents.setWindowOpenHandler(()=>({action:"deny"}));this.view.webContents.on("will-navigate",(event,url)=>{if(!isAllowedRuntimeUrl(url))event.preventDefault()});this.view.webContents.session.setPermissionRequestHandler((_contents,_permission,callback)=>callback(false));this.bindStateEvents()}
async start():Promise<BrowserSnapshot>{await this.view.webContents.loadURL(HOME_URL);return this.snapshot()}
async navigate(input:string):Promise<BrowserSnapshot>{const target=classifyNavigationInput(input);if(target.kind==="blocked"){this.lastError=target.reason;this.emitState();return this.snapshot()}this.lastError=undefined;await this.view.webContents.loadURL(target.url);return this.snapshot()}
back():BrowserSnapshot{if(this.view.webContents.navigationHistory.canGoBack())this.view.webContents.navigationHistory.goBack();return this.snapshot()}
forward():BrowserSnapshot{if(this.view.webContents.navigationHistory.canGoForward())this.view.webContents.navigationHistory.goForward();return this.snapshot()}
reload():BrowserSnapshot{this.view.webContents.reload();return this.snapshot()}
stop():BrowserSnapshot{this.view.webContents.stop();return this.snapshot()}
snapshot():BrowserSnapshot{const wc=this.view.webContents;return{url:wc.getURL(),title:wc.getTitle(),isLoading:wc.isLoading(),canGoBack:wc.navigationHistory.canGoBack(),canGoForward:wc.navigationHistory.canGoForward(),error:this.lastError}}
private layout(bounds:Rectangle):void{this.view.setBounds({x:0,y:CHROME_HEIGHT,width:bounds.width,height:Math.max(0,bounds.height-CHROME_HEIGHT)})}
private bindStateEvents():void{const wc=this.view.webContents;wc.on("did-start-loading",()=>this.emitState());wc.on("did-stop-loading",()=>this.emitState());wc.on("page-title-updated",()=>this.emitState());wc.on("did-navigate",()=>this.emitState());wc.on("did-navigate-in-page",()=>this.emitState());wc.on("did-fail-load",(_event,code,description,validatedURL,isMainFrame)=>{if(isMainFrame&&code!==-3)this.lastError=`${description} · ${validatedURL}`;this.emitState()})}
private emitState():void{if(!this.window.isDestroyed())this.window.webContents.send(ipcChannels.browserStateChanged,this.snapshot())}}
function isAllowedRuntimeUrl(raw:string):boolean{try{const url=new URL(raw);return url.protocol==="https:"||(url.protocol==="http:"&&["localhost","127.0.0.1","[::1]"].includes(url.hostname))}catch{return false}}
