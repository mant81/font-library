# 민보체 Android 앱 / APK

설치 파일: [민보체 APK](../../dist/android/minbo-font-preview-0.1.3.apk). 저장소 기준 경로는 `fonts/minbo/dist/android/minbo-font-preview-0.1.3.apk`다.

Android 8.0(API 26) 이상에서 설치하는 서체 미리보기 앱이다. 문장 입력, 7–72sp 크기 조절, 작은 글자용 보정본 전환, 예제 문장 복원을 제공한다. 인터넷·저장소 등 별도 앱 권한을 요청하지 않는다. 휴대폰의 시스템 기본 글꼴 설정은 변경하지 않는다.

APK를 휴대폰에 복사하여 연다. Android에서 해당 파일을 연 앱의 설치 허용을 요청하면 설정 후 설치한다. 로컬 시험용 인증서로 서명했으며 스토어 배포용 릴리스는 아니다.

## 다시 빌드하기

저장소 루트에서:

```powershell
.\.venv\Scripts\python scripts/build_apk.py --font minbo
```

Android SDK platform 35, Build Tools 36.0.0, JDK 17 이상이 필요하다. 기본 SDK는 `%LOCALAPPDATA%\Android\Sdk`, Java는 PATH에서 찾는다. 다른 위치는 `--sdk 경로 --java-home 경로`로 지정한다. aapt2 → javac → D8 → zipalign → apksigner 순서로 직접 빌드하므로 Gradle 다운로드가 필요 없다.

시험용 서명 키는 저장소 루트의 `.local/android-debug.keystore`에 보관하며 Git에서 제외한다. 같은 앱을 업데이트하려면 이 키를 유지한다. 빌드 결과의 SHA-256·SDK 범위·서명 검사 결과는 이 폰트 폴더의 `dist/android/apk-manifest.json`에 기록한다.

## 검증

`scripts/check_apk.py`는 설치된 Android 36 Google APIs x86_64 시스템 이미지로 프로젝트 전용 headless AVD를 만들어 테스트한다. 기존 에뮬레이터나 실제 휴대폰은 대상으로 삼지 않는다.

```powershell
.\.venv\Scripts\python scripts/check_apk.py --font minbo
```

설치·실행·두 TTF 로딩·7sp 버튼·보정본 자동 선택·실시간 문장 입력·충돌 로그 검사를 통과했다. 증거는 `docs/android/validation.json`, `app-initial.png`, `app-7sp.png`에 있다. 실제 휴대폰 검증은 미실행이다.

## 기존 앱에 폰트만 적용하기

`python scripts/package_android.py`는 구조 검사를 통과한 웹용 TTF 마스터를 `app/src/main/res/font/`에 그대로 복사하고 SHA-256을 대조한다.

기존 Android 앱에 두 TTF를 복사한 뒤 API 26 이상에서 다음과 같이 사용한다.

```java
textView.setTypeface(getResources().getFont(R.font.minbo_regular));
// 작은 크기에는 보정본을 선택한다.
textView.setTypeface(getResources().getFont(R.font.minbo_small));
```

`app/src/main/java/com/example/yumifont/MainActivity.java`는 현재 APK의 실제 화면 코드다. 기존 앱에 가져갈 때는 패키지 이름과 R 참조를 대상 앱에 맞춘다. 이 디렉터리는 SDK 직접 빌드 방식이며 Gradle 프로젝트는 아니다.

Android의 sp는 웹 CSS px와 동일한 단위가 아니다. 예제의 7sp는 별도 기기 검증이 필요하며, 웹의 7px 검증 결과로 Android 품질을 통과 처리하지 않는다. 시스템 폰트 교체나 제조사 테마 설치 패키지는 포함하지 않는다.

현재 상태: 서명된 APK 생성, Android 36 에뮬레이터 검사 통과. Android 실기기 및 최소 API 26 환경의 런타임 검증은 미실행.
