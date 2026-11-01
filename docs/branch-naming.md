# 브랜치·폰트 명명 규칙

여러 폰트를 하나의 `main` 브랜치에 계속 추가한다. 폰트는 `fonts/<font-id>/` 폴더로 구분한다. 폰트 식별자는 영문 소문자와 하이픈을 사용한다. 현재 폰트는 `minbo`, 표시 이름은 `minbo체`, 영문 family는 `Minbo`다.

| 용도 | 브랜치 |
|---|---|
| 기본 | `main` |
| 여러 폰트의 공통 기능 | `feat/multi-font-support` |
| minbo체 개발·추가 | `feat/fonts/minbo` |
| 다른 폰트 추가 | `feat/fonts/<font-id>` |
| 특정 폰트 수정 | `fix/fonts/<font-id>/<issue>` |

다른 폰트도 고유한 font-id와 family 이름을 부여한다. `fonts/<font-id>/config/font.json`의 id, display_name, family, file_prefix를 명명의 기준으로 삼는다. 공통 도구는 `--font <font-id>`로 대상을 선택한다. 여러 폰트를 한꺼번에 빌드하는 명령은 별도 구현 대상이다. 위 기능 브랜치는 필요한 경우 잠시 사용하며 지속 보관 위치는 main이다.

저장소는 `mant81/font-library`이며 지속 관리 브랜치는 `main`이다. 폰트마다 브랜치를 새로 만들지 않고 폴더를 추가한다.
