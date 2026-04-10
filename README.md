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

<p align="center"><b>STAR ENGINE PROJECT</b>가 개발한 대전형 카드 배틀 주사위 보드게임 <b>Astral Party</b>의 비공식 유저 한국어 패치입니다!</p>

<div align="center">
  
[![][discord-shield]][discord-link]

</div>

<div align="center">
  
[![][version-shield]][release-link]
[![][ci-shield]][ci-link]
[![][python-shield]][python-link]
[![][steam-shield]][steam-link]

</div>

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

> © 2023 Shanghai Electric Cicada. All rights reserved.

> [!TIP]
> 누구나 [번역 에디터](https://astral.maynutlab.com/editor)를 통해 번역에 참여하실 수 있습니다. 개선이 필요한 번역을 발견한다면 언제든지 의견을 남겨 주세요.

> [!WARNING]
> **Pre-release** 버전에서는 일부 번역되지 않은 요소가 존재할 수 있습니다.

## 어떻게 적용하나요?

|버전|파일명|적용 방법|비고|
|----|-----|---------|----|
|Steam 글로벌 버전|INT_STEAM|[적용 방법]()|[자동 패치 프로그램 지원](https://github.com/maynut02/AstralAutoPatcher)|
|Android 일본 버전|INT_ANDROID|[적용 방법]()|
|BiliBili PC 버전|CN_BILIBILI|[적용 방법]()|[자동 패치 프로그램 지원](https://github.com/maynut02/AstralAutoPatcher)|

## 자동화

- [Data Sync](/.github/workflows/data-sync.yml) 작업은 Google Cloud Scheduler를 통해 10분마다 실행됩니다.
- [Actions 작업 결과](https://github.com/maynut02/astralparty-korean-patch/tree/workflow)

## 개발 진행도
- [x] Steam 글로벌 버전(INT_STEAM)
- [ ] Steam 중국 버전(CN_STEAM)
- [x] Android 일본 버전(INT_ANDROID)
- [ ] iOS 일본 버전(INT_IOS)
- [x] BiliBili PC 버전(CN_BILIBILI)
- [ ] BiliBili Android 버전(?)
- [ ] WeGame 버전(CN_WEGAME)

## 개발자용

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


<!-- Link Definitions -->
[discord-shield]: https://img.shields.io/badge/Discord-업데이트_알림_받기-ECF3FF?style=flat-square&logo=discord&logoColor=ffffff&labelColor=000000
[discord-link]: https://discord.gg/khYThH3gPD

[version-shield]: https://img.shields.io/github/v/release/maynut02/astralparty-korean-patch?style=flat-square&color=ECF3FF&labelColor=000000
[release-link]: https://github.com/maynut02/astralparty-korean-patch/releases
[python-shield]: https://img.shields.io/badge/python-3.1.2+-ECF3FF?style=flat-square&logo=python&logoColor=ffffff&labelColor=000000
[python-link]: https://www.python.org/
[ci-shield]: https://img.shields.io/github/actions/workflow/status/maynut02/astralparty-korean-patch/data-sync.yml?style=flat-square&color=ECF3FF&labelColor=000000
[ci-link]: https://github.com/maynut02/astralparty-korean-patch/actions
[steam-shield]: https://img.shields.io/badge/Astral_Party-ECF3FF?style=flat-square&logo=steam&logoColor=ffffff&labelColor=000000
[steam-link]: https://store.steampowered.com/app/2622000/Astral_Party/
