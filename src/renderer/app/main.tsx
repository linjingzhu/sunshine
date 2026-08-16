import React from "react";
import ReactDOM from "react-dom/client";
import "../theme/tokens.css";
import "./styles.css";

function App(): React.JSX.Element {
  const [version, setVersion] = React.useState("확인 중");
  React.useEffect(() => {
    void window.sunshine?.executeCommand({ id: "app.getVersion" }).then((result) => {
      setVersion(result.ok ? result.value ?? "알 수 없음" : "연결 실패");
    });
  }, []);

  return (
    <main className="shell">
      <section className="welcome" aria-labelledby="welcome-title">
        <div className="mark" aria-hidden="true">☀</div>
        <p className="eyebrow">SUNSHINE OS</p>
        <h1 id="welcome-title">브라우저의 기반을 준비했습니다.</h1>
        <p className="description">안전한 Chromium 경계와 명령 시스템 위에서, 평범한 웹 브라우징부터 차근차근 시작합니다.</p>
        <p className="status" role="status"><span /> Wave 0 · Runtime v{version}</p>
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
