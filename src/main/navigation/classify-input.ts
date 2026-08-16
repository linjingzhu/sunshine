const HAS_SCHEME = /^[a-zA-Z][a-zA-Z\d+.-]*:/;
const LOCALHOST = /^(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?(?:\/|$)/i;
const DOMAIN = /^(?:[a-z\d](?:[a-z\d-]{0,61}[a-z\d])?\.)+[a-z]{2,63}(?::\d+)?(?:\/[^\s]*)?$/i;
export type NavigationTarget={kind:"url";url:string}|{kind:"search";url:string;query:string}|{kind:"blocked";reason:string};
export function classifyNavigationInput(rawInput:string):NavigationTarget{const input=rawInput.trim();if(!input)return{kind:"blocked",reason:"주소나 검색어를 입력하세요."};if(LOCALHOST.test(input))return{kind:"url",url:`http://${input}`};if(HAS_SCHEME.test(input)){try{const parsed=new URL(input);if(parsed.protocol==="https:")return{kind:"url",url:parsed.toString()};if(parsed.protocol==="http:"&&["localhost","127.0.0.1","[::1]"].includes(parsed.hostname))return{kind:"url",url:parsed.toString()};return{kind:"blocked",reason:"HTTPS 주소만 열 수 있습니다."}}catch{return toSearch(input)}}if(DOMAIN.test(input))return{kind:"url",url:`https://${input}`};return toSearch(input)}
function toSearch(query:string):NavigationTarget{return{kind:"search",query,url:`https://www.google.com/search?q=${encodeURIComponent(query)}`}}
