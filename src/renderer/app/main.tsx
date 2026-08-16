import React from "react";
import ReactDOM from "react-dom/client";
import type { BrowserSnapshot, CommandRequest } from "../../shared/commands/command";
import "../theme/tokens.css";
import "./styles.css";

const EMPTY_STATE: BrowserSnapshot = { url: "", title: "새 탭", isLoading: true, canGoBack: false, canGoForward: false };

function App(): React.JSX.Element {
  const [browser, setBrowser] = React.useState(EMPTY_STATE);
  const [address, setAddress] = React.useState("");
  const [editing, setEditing] = React.useState(false);
  const addressRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    const api = window.sunshine;
    if (!api) return;
    const unsubscribe = api.onBrowserStateChanged(setBrowser);
    void api.executeCommand({ id: "browser.getState" }).then((result) => {
      if (result.ok && result.browser) setBrowser(result.browser);
    });
    return unsubscribe;
  }, []);

  React.useEffect(() => { if (!editing) setAddress(browser.url); }, [browser.url, editing]);
  React.useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "l") {
        event.preventDefault();
        addressRef.current?.focus();
        addressRef.current?.select();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const execute = async (request: CommandRequest) => {
    const result = await window.sunshine?.executeCommand(request);
    if (result?.ok && result.browser) setBrowser(result.browser);
  };
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setEditing(false);
    void execute({ id: "browser.navigate", input: address });
  };

  return (
    <main className="browser-chrome">
      <header className="tab-strip">
        <div className="brand" aria-label="Sunshine OS"><span aria-hidden="true">☀</span></div>
        <div className="tab active" aria-current="page">
          <span className={browser.isLoading ? "tab-spinner spinning" : "tab-spinner"} aria-hidden="true">◌</span>
          <span className="tab-title">{browser.title || "새 탭"}</span>
          <button className="tab-close" aria-label="현재 탭 닫기" disabled>×</button>
        </div>
        <button className="new-tab" aria-label="새 탭" title="다중 탭은 다음 개발 단계에서 지원합니다." disabled>+</button>
        <div className="window-drag-space" />
      </header>
      <nav className="toolbar" aria-label="브라우저 도구 모음">
        <button className="icon-button" aria-label="뒤로" title="뒤로" disabled={!browser.canGoBack} onClick={() => void execute({ id: "browser.back" })}>←</button>
        <button className="icon-button" aria-label="앞으로" title="앞으로" disabled={!browser.canGoForward} onClick={() => void execute({ id: "browser.forward" })}>→</button>
        <button className="icon-button" aria-label={browser.isLoading ? "불러오기 중지" : "새로고침"} title={browser.isLoading ? "중지" : "새로고침"} onClick={() => void execute({ id: browser.isLoading ? "browser.stop" : "browser.reload" })}>{browser.isLoading ? "×" : "↻"}</button>
        <form className="omnibox" onSubmit={submit}>
          <span className="security-indicator" title="HTTPS 보안 연결" aria-hidden="true">{browser.url.startsWith("https:") ? "●" : "○"}</span>
          <label className="sr-only" htmlFor="address">주소 또는 검색어</label>
          <input id="address" ref={addressRef} value={address} onChange={(event) => setAddress(event.target.value)} onFocus={() => setEditing(true)} onBlur={() => setEditing(false)} placeholder="주소를 검색하거나 입력하세요" autoComplete="off" spellCheck={false} />
        </form>
        <button className="icon-button menu" aria-label="Sunshine 메뉴" title="메뉴 준비 중" disabled>⋮</button>
      </nav>
      {browser.error && <div className="error-toast" role="alert">{browser.error}</div>}
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
