```diff
+ Pynecone을 찾고 계신가요? 이곳이 맞습니다. Pynecone은 이제 Reflex로 불립니다. +
```

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg#gh-light-mode-only" alt="Reflex Logo" width="300px">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg#gh-dark-mode-only" alt="Reflex Logo" width="300px">

<hr>

### **✨ 순수 Python으로 고성능 사용자 정의 웹앱을 만들어 보세요. 몇 초만에 배포 가능합니다. ✨**
[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![versions](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentaiton](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)
</div>

---
[English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md) | [Türkçe](https://github.com/reflex-dev/reflex/blob/main/docs/tr/README.md) | [हिंदी](https://github.com/reflex-dev/reflex/blob/main/docs/in/README.md) | [Português (Brasil)](https://github.com/reflex-dev/reflex/blob/main/docs/pt/pt_br/README.md) | [Italiano](https://github.com/reflex-dev/reflex/blob/main/docs/it/README.md) | [한국어](https://github.com/reflex-dev/reflex/blob/main/docs/kr/README.md) | [日本語](https://github.com/reflex-dev/reflex/blob/main/docs/ja/README.md) | [Deutsch](https://github.com/reflex-dev/reflex/blob/main/docs/de/README.md) | [Persian (پارسی)](https://github.com/reflex-dev/reflex/blob/main/docs/pe/README.md)
---
## ⚙️ 설치

터미널을 열고 실행하세요. (Python 3.9+ 필요):

```bash
pip install reflex
```

## 🥳 첫 앱 만들기

`reflex`를 설치하면, `reflex` 명령어 라인 도구도 설치됩니다.

새 프로젝트를 생성하여 설치가 성공적인지 확인합니다. (`my_app_name`을 프로젝트 이름으로 변경합니다.):

```bash
mkdir my_app_name
cd my_app_name
reflex init
```

이 명령어는 새 디렉토리에 템플릿 앱을 초기화합니다.

개발 모드에서 이 앱을 실행할 수 있습니다:

```bash
reflex run
```

http://localhost:3000 에서 앱이 실행 됩니다.

이제 `my_app_name/my_app_name.py`에서 소스코드를 수정할 수 있습니다. Reflex는 빠른 새로고침을 지원하므로 코드를 저장할 때마다 즉시 변경 사항을 볼 수 있습니다.


## 🫧 예시 앱

예시를 살펴보겠습니다: DALL·E를 중심으로 이미지 생성 UI를 만들어 보겠습니다. 간단하게 하기 위해 OpenAI API를 호출했지만, 이를 로컬에서 실행되는 ML 모델로 대체할 수 있습니다.

&nbsp;

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/dalle.gif" alt="A frontend wrapper for DALL·E, shown in the process of generating an image." width="550" />
</div>

&nbsp;

이것이 완성된 코드입니다. 이 모든 것은 하나의 Python 파일에서 이루어집니다!

```python
import reflex as rx
import openai

openai_client = openai.OpenAI()


class State(rx.State):
    """The app state."""

    prompt = ""
    image_url = ""
    processing = False
    complete = False

    def get_image(self):
        """Get the image from the prompt."""
        if self.prompt == "":
            return rx.window_alert("Prompt Empty")

        self.processing, self.complete = True, False
        yield
        response = openai_client.images.generate(
            prompt=self.prompt, n=1, size="1024x1024"
        )
        self.image_url = response.data[0].url
        self.processing, self.complete = False, True


def index():
    return rx.center(
        rx.vstack(
            rx.heading("DALL-E", font_size="1.5em"),
            rx.input(
                placeholder="Enter a prompt..",
                on_blur=State.set_prompt,
                width="25em",
            ),
            rx.button(
                "Generate Image", 
                on_click=State.get_image,
                width="25em",
                loading=State.processing
            ),
            rx.cond(
                State.complete,
                rx.image(src=State.image_url, width="20em"),
            ),
            align="center",
        ),
        width="100%",
        height="100vh",
    )

# Add state and page to the app.
app = rx.App()
app.add_page(index, title="Reflex:DALL-E")
```

## 하나씩 살펴보겠습니다.

### **Reflex UI**

UI부터 시작해봅시다.

```python
def index():
    return rx.center(
        ...
    )
```

`index` 함수는 앱의 프론트엔드를 정의합니다.

`center`, `vstack`, `input`, `button`과 같은 다양한 컴포넌트를 사용하여 프론트엔드를 구축합니다. 
컴포넌트들은 복잡한 레이아웃을 만들기 위해 서로 중첩될 수 있습니다. 
그리고 키워드 인자를 사용하여 CSS의 모든 기능을 사용하여 스타일을 지정할 수 있습니다.


Reflex는 시작하기 위한 [60개 이상의 기본 컴포넌트](https://reflex.dev/docs/library)를 제공하고 있습니다. 더 많은 컴포넌트를 추가하고 있으며, [자신만의 컴포넌트를 생성하는 것](https://reflex.dev/docs/wrapping-react/overview/)도 쉽습니다.

### **State**

Reflex는 UI를 State 함수로 표현합니다.

```python
class State(rx.State):
    """The app state."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False
```

state는 앱에서 변경될 수 있는 모든 변수(vars로 불림)와 이러한 변수를 변경하는 함수를 정의합니다.

여기서 state는 `prompt`와 `image_url`로 구성됩니다. 또한 `processing`과 `complete`라는 불리언 값이 있습니다. 이 값들은 이미지 생성 중 버튼을 비활성화할 때와, 결과 이미지를 표시할 때를 나타냅니다.

### **Event Handlers**

```python
def get_image(self):
    """Get the image from the prompt."""
    if self.prompt == "":
        return rx.window_alert("Prompt Empty")

    self.processing, self.complete = True, False
    yield
    response = openai_client.images.generate(
        prompt=self.prompt, n=1, size="1024x1024"
    )
    self.image_url = response.data[0].url
    self.processing, self.complete = False, True
```

State 내에서, state vars를 변경하는 이벤트 핸들러라고 불리는 함수를 정의합니다. 이벤트 핸들러는 Reflex에서 state를 변경하는 방법입니다. 버튼을 클릭하거나 텍스트 상자에 입력하는 것과 같이 사용자 동작에 응답하여 호출될 수 있습니다. 이러한 동작을 이벤트라고 합니다.

DALL·E. 앱에는 OpenAI API에서 이미지를 가져오는 `get_image` 이벤트 핸들러가 있습니다. 이벤트 핸들러의 중간에 `yield`를 사용하면 UI가 업데이트됩니다. 그렇지 않으면 UI는 이벤트 핸들러의 끝에서 업데이트됩니다.

### **Routing**

마지막으로, 앱을 정의합니다.

```python
app = rx.App()
```

앱의 루트에서 index 컴포넌트로 페이지를 추가합니다. 또한 페이지 미리보기/브라우저 탭에 표시될 제목도 추가합니다.

```python
app.add_page(index, title="DALL-E")
```

여러 페이지를 추가하여 멀티 페이지 앱을 만들 수 있습니다.

## 📑 자료

<div align="center">

📑 [문서](https://reflex.dev/docs/getting-started/introduction) &nbsp; |  &nbsp; 🗞️ [블로그](https://reflex.dev/blog) &nbsp; |  &nbsp; 📱 [컴포넌트 라이브러리](https://reflex.dev/docs/library) &nbsp; |  &nbsp; 🖼️ [갤러리](https://reflex.dev/docs/gallery) &nbsp; |  &nbsp; 🛸 [배포](https://reflex.dev/docs/hosting/deploy)  &nbsp;   

</div>





## ✅ 상태

Reflex는 2022년 12월 Pynecone이라는 이름으로 출시되었습니다.

2023년 7월 현재, 우리는 **Public Beta** 상태에 있습니다.

-   :white_check_mark: **Public Alpha**: 누구나 Reflex를 설치하고 사용할 수 있습니다. 문제가 발생할 수도 있지만 적극적으로 수정합니다.
-   :large_orange_diamond: **Public Beta**: 비상업적 용도로 충분히 안정적입니다.
-   **Public Hosting Beta**: _선택적으로_, Reflex에서 앱을 배포하고 호스팅할 수 있습니다!
-   **Public** : Reflex는 프로덕션 준비를 마쳤습니다.

Reflex는 매주 새로운 릴리즈와 기능을 제공합니다! 최신 정보를 확인하려면 :star: Star와 :eyes: Watch를 눌러 이 저장소를 확인하세요.

## 기여

우리는 모든 기여를 환영합니다! 아래는 Reflex 커뮤니티에 참여하는 좋은 방법입니다.

-   **Discord 참여**: 우리의 [Discord](https://discord.gg/T5WSbC2YtQ)는 Reflex 프로젝트에 대한 도움을 받고 기여하는 방법을 논의하는 최고의 장소입니다.
-   **GitHub Discussions**: 추가하고 싶은 기능이나 혼란스럽거나 해결이 필요한 것들에 대해 이야기하는 좋은 방법입니다.
-   **GitHub Issues**: 이것은 버그를 보고하는 훌륭한 방법입니다. 또한, 기존의 이슈를 해결하고 PR을 제출할 수 있습니다.

우리는 능력이나 경험에 상관없이 적극적으로 기여자를 찾고 있습니다.

## License

Reflex는 오픈소스이며 [Apache License 2.0](LICENSE)로 라이선스가 부여됩니다.
