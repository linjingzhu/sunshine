# macOS 테스트 빌드

## 지원 범위

GitHub Actions의 **macOS Test Build** 작업은 Intel Mac과 Apple Silicon Mac에서 실행할 수 있는 Universal 테스트 빌드를 생성합니다.

생성물:

- `Sunshine-OS-<version>-mac-universal.dmg`
- `Sunshine-OS-<version>-mac-universal.zip`

## GitHub에서 받기

1. 저장소의 **Actions** 탭을 엽니다.
2. **macOS Test Build** 작업을 선택합니다.
3. 성공한 실행의 **Artifacts**에서 `sunshine-os-macos-universal-unsigned`를 다운로드합니다.
4. 압축을 푼 뒤 DMG를 열고 Sunshine OS를 Applications 폴더로 옮깁니다.

## 첫 실행

현재 파일은 개발 테스트용이며 Apple Developer ID로 서명하거나 공증하지 않았습니다. 따라서 macOS가 일반적인 더블클릭 실행을 막을 수 있습니다.

테스트 대상 앱을 Finder에서 Control-클릭하고 **열기**를 선택한 뒤, 확인 대화상자에서 다시 **열기**를 선택합니다. 출처를 신뢰할 수 있는 이 저장소의 Actions 아티팩트에만 이 절차를 사용하세요.

## 로컬 macOS 빌드

Node.js 22 환경에서 다음을 실행합니다.

```bash
npm ci
npm test
npm run typecheck
npm run package:mac
```

결과는 `release/`에 생성됩니다.

## 출시 전 필수 작업

- 전용 앱 아이콘과 `icns` 자산 추가
- Apple Developer ID Application 인증서로 코드 서명
- Apple 공증(Notarization) 및 stapling
- Intel Mac과 Apple Silicon Mac의 실제 기기 스모크 테스트
- 자동 업데이트 채널 및 릴리스 무결성 정책 설계
