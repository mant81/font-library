# 민보체 / minbo font 0.1.2 시험판

현대 한글 11,172자 + 호환 자모 51자 + ASCII 95자. 원본의 76개 자모·영문 표본을 직접 추적했고, 숫자·문장부호는 필체에 맞춰 새로 제작했다.

## 웹 적용

CSS와 폰트 파일의 상대 경로를 유지한다. 전체 파일은 `minbo.css`, 작은 글자용은 `minbo-small.css`다. 분할 방식은 각각 `minbo-subset.css`, `minbo-small-subset.css`를 사용한다. 한 페이지에서 전체/분할 중 하나만 선택한다.

```html
<link rel="stylesheet" href="/fonts/minbo.css">
<link rel="stylesheet" href="/fonts/minbo-small.css">
<style>
  .handwriting { font-family: 'minbo font', sans-serif; font-weight: 400; }
  .handwriting-small { font-family: 'minbo font Small', sans-serif; font-weight: 400; }
</style>
```

7px 등 15px 이하에는 `minbo font Small`을 선택한다. 글자 크기에 따른 선택은 적용 사이트에서 처리한다. 미리보기 예제는 자동 전환을 제공한다. 7px의 전수 렌더 검사는 글자 소실·잘림·저대비를 확인하며 모든 문자의 식별성을 보증하지 않는다. 상세 결과는 `docs/browser-validation.json`과 확대 검토 이미지를 참조한다.

입력은 NFC로 정규화한다(`text.normalize('NFC')`). NFD 자모 조판·옛한글·한자·이모지·ASCII 밖 기호는 지원 범위가 아니다. 지원하지 않는 문자는 지정한 대체 서체로 표시한다.

TTF는 Android 앱 내부 리소스에도 사용할 수 있다. 직접 쓴 손글씨를 바탕으로 독자 제작했다. 상업적 이용·수정·재배포 허락 범위는 별도 결정 대상이며, 시험판은 최종 시각 검토 전이다.
