<picture>
  <source
    width="100%"
    srcset="./docs/img/banner_1280x420.png"
    media="(prefers-color-scheme: dark)"
  />
  <source
    width="100%"
    srcset="./docs/img/banner_1280x420.png"
    media="(prefers-color-scheme: light), (prefers-color-scheme: no-preference)"
  />
  <img width="250" src="./docs/img/banner_1280x420.png" />
</picture>

<h1 align="center">아스트랄 파티 비공식 한글패치</h1>

<p align="center">**STAR ENGINE PROJECT**가 개발한 대전형 카드 배틀 주사위 보드게임 **Astral Party**의 비공식 유저 한국어 패치입니다!</p>

<p float="left" align="center">
  <!-- downloads -->
  <a href="https://astral.maynutlab.com/">
    <picture>
      <source
        width="30%"
        srcset="./docs/img/downloads_links_1280x420.png"
        media="(prefers-color-scheme: dark)"
      />
      <source
        width="30%"
        srcset="./docs/img/downloads_links_1280x420.png"
        media="(prefers-color-scheme: light), (prefers-color-scheme: no-preference)"
      />
      <img width="30%" src="./docs/img/downloads_links_1280x420.png" />
    </picture>
  </a>

  <!-- autopatcher -->
  <a href="https://github.com/maynut02/AstralAutoPatcher">
    <picture>
      <source
        width="30%"
        srcset="./docs/img/autopatcher_links_1280x420.png"
        media="(prefers-color-scheme: dark)"
      />
      <source
        width="30%"
        srcset="./docs/img/autopatcher_links_1280x420.png"
        media="(prefers-color-scheme: light), (prefers-color-scheme: no-preference)"
      />
      <img width="30%" src="./docs/img/autopatcher_links_1280x420.png" />
    </picture>
  </a>

  <!-- editor -->
  <a href="https://astral.maynutlab.com/editor">
    <picture>
      <source
        width="30%"
        srcset="./docs/img/editor_links_1280x420.png"
        media="(prefers-color-scheme: dark)"
      />
      <source
        width="30%"
        srcset="./docs/img/editor_links_1280x420.png"
        media="(prefers-color-scheme: light), (prefers-color-scheme: no-preference)"
      />
      <img width="30%" src="./docs/img/editor_links_1280x420.png" />
    </picture>
  </a>
</p>

> [!TIP]
> 누구나 [번역 에디터](astral.maynutlab.com/editor)를 통해 번역에 참여하실 수 있습니다. 개선이 필요한 번역을 발견한다면 언제든지 의견을 남겨 주세요.

> [!WARNING]
> **Pre-release** 버전에서는 일부 번역되지 않은 요소가 존재할 수 있습니다.

## How to use

### Steam 글로벌 버전

- 파일명: INT_STEAM

### Android 일본 버전

- 파일명: INT_ANDROID

### BiliBili PC 버전

- 파일명: CN_BILIBILI

## Current Progress
- [x] Steam 글로벌 버전(INT_STEAM)
- [ ] Steam 중국 버전(CN_STEAM)
- [x] Android 일본 버전(INT_ANDROID)
- [ ] iOS 일본 버전(INT_IOS)
- [x] BiliBili PC 버전(CN_BILIBILI)
- [ ] BiliBili Android 버전(?)
- [ ] WeGame 버전(CN_WEGAME)

## Development

설치:

```bash
python -m pip install -e .
```

실행:

```bash
astral-patch get --version 3.0.1 --route INT_STEAM
astral-patch lang
astral-patch str
astral-patch patch --route INT_STEAM
astral-workflow build-patch-zips
```