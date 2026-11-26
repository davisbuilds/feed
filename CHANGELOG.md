# Changelog

## [0.4.0](https://github.com/davisbuilds/feed/compare/v0.3.3...v0.4.0) (2026-11-26)


### ⚠ BREAKING CHANGES

* **cli:** report credential presence without key prefixes ([#102](https://github.com/davisbuilds/feed/issues/102))
* **cli:** feed config --json replaces llm_api_key, openai_api_key, and resend_api_key with boolean fields suffixed _configured. Use provider_api_key_configured for the selected LLM provider.

### Bug Fixes

* **cli:** report credential presence without key prefixes ([6bbf873](https://github.com/davisbuilds/feed/commit/6bbf87391764424e24b50ca4986629379faef0b4))
* **cli:** report credential presence without key prefixes ([#102](https://github.com/davisbuilds/feed/issues/102)) ([ff66031](https://github.com/davisbuilds/feed/commit/ff66031844ca0778bed28fc3ee1222df04cb4411))

## [0.3.3](https://github.com/davisbuilds/feed/compare/v0.3.2...v0.3.3) (2026-11-23)


### Bug Fixes

* **cli:** keep digest JSON stdout parseable ([50bc927](https://github.com/davisbuilds/feed/commit/50bc927a6ebb4ee3e935e79cf3dcaf309ca5bcfd))
* **cli:** keep digest JSON stdout parseable ([#95](https://github.com/davisbuilds/feed/issues/95)) ([57c76cf](https://github.com/davisbuilds/feed/commit/57c76cf86595b953d72079216f3f5ba4eb981b22))
* **cli:** resolve setup and scheduler paths from the checkout ([648adaf](https://github.com/davisbuilds/feed/commit/648adaff1bf7b51702867246aa138610aa7dbac2))
* **cli:** restore provider choices in setup wizard ([4ce9837](https://github.com/davisbuilds/feed/commit/4ce98379d715c0b19f18411c4027d1673760527d))
* **cli:** restore provider choices in setup wizard ([#100](https://github.com/davisbuilds/feed/issues/100)) ([111d9be](https://github.com/davisbuilds/feed/commit/111d9be788d3bba0ac16ff0077257b8be9f2a251))
* **gemini:** preserve beta API with SDK v3 ([de0ba03](https://github.com/davisbuilds/feed/commit/de0ba033e6e01bda3315ba41124d2629302a278a))
* **gemini:** preserve beta API with SDK v3 ([#101](https://github.com/davisbuilds/feed/issues/101)) ([0582fe4](https://github.com/davisbuilds/feed/commit/0582fe48e23caa5a2102fce98e7f6d8cad4847e4))

## [0.3.2](https://github.com/davisbuilds/feed/compare/v0.3.1...v0.3.2) (2026-10-26)


### Bug Fixes

* **deps:** upgrade certifi to 2026.10.19 for the emSign CA distrust ([f75604a](https://github.com/davisbuilds/feed/commit/f75604a1e74a9574f0460b68a2a578867eba8723))

## [0.3.1](https://github.com/davisbuilds/feed/compare/3461c4023b0b3dd873bc012b232abee940331ce7...v0.3.1) (2026-09-26)


### Bug Fixes

* **cli:** report installed package version ([abb7b08](https://github.com/davisbuilds/feed/commit/abb7b088484529336a557da602429f81ada8c1e8))
