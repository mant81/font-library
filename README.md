# Font Library

[웹사이트](https://mant81.github.io/font-library/) · [APK 릴리즈](https://github.com/mant81/font-library/releases/tag/minbo-v0.1.1)

하나의 `main` 브랜치에서 여러 폰트를 폴더별로 관리한다. 각 폰트의 원본·설정·글리프·배포물·문서·예제는 `fonts/<font-id>/` 안에 둔다.

```text
fonts/
  minbo/
    assets/source/       원본 이미지와 출처
    config/              폰트 정보·조합 보정 설정
    sources/             글리프·중심선·조합 레시피
    dist/                TTF·WOFF2·CSS·Android APK
    docs/                PRD·설계·검증 보고서·검토 이미지
    examples/            웹 미리보기·Android 앱 소스
    README.md
scripts/                 공통 제작·검증 도구
tests/                   공통 회귀 검사
harness/                 공통 파이프라인 정의
docs/                    저장소 공통 규칙
```

## 폰트 목록

| ID | 이름 | 안내 | 웹 미리보기 | Android APK |
|---|---|---|---|---|
| `minbo` | minbo체 | [폰트 안내](fonts/minbo/README.md) | [미리보기](http://127.0.0.1:8765/fonts/minbo/examples/web/) | [0.1.1 APK](fonts/minbo/dist/android/minbo-font-preview-0.1.1.apk) |

## 실행

아래 제작 명령은 원본 자료를 보유한 로컬 환경의 저장소 루트에서 실행한다. 원본 손글씨 이미지·추출 글리프와 provenance·상세 검토 자료는 공개 저장소에서 제외한다. 공개 clone만으로 원본 제작을 재현할 수는 없으며, Pages와 APK 릴리즈는 공개된 검증 산출물로 동작한다.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python scripts/run.py --font minbo
.\.venv\Scripts\python scripts/build_apk.py --font minbo
```

개별 도구에서도 `--font <font-id>`를 사용할 수 있다. 생략 시 기본값은 `minbo`다. 선택한 폴더의 config/font.json에 적힌 id가 폴더 이름과 같아야 하며, 알 수 없는 폰트를 선택하면 실패한다.

웹 미리보기:

```powershell
.\.venv\Scripts\python -m http.server 8765 --bind 127.0.0.1
```

<http://127.0.0.1:8765/fonts/minbo/examples/web/>를 연다.

## 새 폰트 추가

1. `fonts/<font-id>/` 아래에 위 폴더 구조를 만든다.
2. config/font.json의 id·display_name·family·file_prefix와 원본 경로를 설정한다.
3. 해당 원본에 맞는 글리프 자료와 예제를 준비한다. 현재 추출/조합 방식은 minbo체 표본 규격을 기준으로 하므로 다른 표본 형식은 별도 대응이 필요하다.
4. `scripts/run.py --font <font-id>`로 선택한 폴더에서 생성·검증한다.
5. 이 목록에 새 폰트를 추가한다.

현재 제공하는 실제 폰트는 minbo체 하나다. 시각적 전수 가독성·Android 실기기·Safari/Firefox 검토는 남아 있다. 자세한 검증 범위와 라이선스 상태는 폰트별 README를 참조한다.

저장소는 `mant81/font-library`, 로컬 작업 위치는 `D:\ai\font-library`다. GitHub에서는 `main` 브랜치에 폰트 폴더를 계속 추가하는 방식으로 운영한다. [명명 규칙](docs/branch-naming.md)을 참조한다.

## Pages와 APK 릴리즈

`site/`의 정적 페이지는 `scripts/build_pages.py`가 폰트별 설정과 배포 파일을 모아 `_site/`로 만든다. 원본 이미지·개인 키·SDK 캐시·머신별 보고서는 Pages 산출물에서 제외한다. 폰트를 추가하면 목록도 자동으로 늘어난다.

```powershell
python scripts/build_pages.py
python -m http.server 8765 --bind 127.0.0.1 --directory _site
```

`main`에 push하면 `.github/workflows/pages.yml`이 GitHub Pages를 배포한다. APK는 검증한 파일과 SHA-256을 함께 GitHub Release에 첨부한다. 폰트별 태그는 `<font-id>-v<version>`이며, 현재 시험판은 `minbo-v0.1.1`이다. Actions의 **Publish Android APK Release**를 수동 실행하거나, 인증된 로컬 환경에서 `python scripts/publish_release.py --font minbo`를 실행한다. 버전이 같으면서 내용이 다른 기존 릴리즈 파일은 덮어쓰지 않는다.
