```diff
+ دنبال Pynecone میگردی؟ شما در مخزن درستی قرار داری. Pynecone به Reflex تغییر نام داده است. +
```

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg#gh-light-mode-only" alt="Reflex Logo" width="300px">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg#gh-dark-mode-only" alt="Reflex Logo" width="300px">

<hr>

### **✨ برنامه های تحت وب قابل تنظیم، کارآمد تماما پایتونی که در چند ثانیه مستقر(دپلوی) می‎شود. ✨**
[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![versions](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentation](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)
</div>

---

[English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md) | [Türkçe](https://github.com/reflex-dev/reflex/blob/main/docs/tr/README.md) | [हिंदी](https://github.com/reflex-dev/reflex/blob/main/docs/in/README.md) | [Português (Brasil)](https://github.com/reflex-dev/reflex/blob/main/docs/pt/pt_br/README.md) | [Italiano](https://github.com/reflex-dev/reflex/blob/main/docs/it/README.md) | [Español](https://github.com/reflex-dev/reflex/blob/main/docs/es/README.md) | [한국어](https://github.com/reflex-dev/reflex/blob/main/docs/kr/README.md) | [日本語](https://github.com/reflex-dev/reflex/blob/main/docs/ja/README.md) | [Deutsch](https://github.com/reflex-dev/reflex/blob/main/docs/de/README.md) | [Persian (پارسی)](https://github.com/reflex-dev/reflex/blob/main/docs/pe/README.md)

---

# Reflex - رفلکس

رفلکس(Reflex) یک کتابخانه برای ساخت برنامه های وب فول استک تماما پایتونی است.

ویژگی های کلیدی:
* **تماما پایتونی** - فرانت اند و بک اند برنامه خود را همه در پایتون بنویسید، بدون نیاز به یادگیری جاوا اسکریپت.
* **انعطاف پذیری کامل** - شروع به کار با Reflex آسان است، اما می تواند به برنامه های پیچیده نیز تبدیل شود.
* **دپلوی فوری** - پس از ساخت، برنامه خود را با [یک دستور](https://reflex.dev/docs/hosting/deploy-quick-start/) دپلوی کنید یا آن را روی سرور خود میزبانی کنید.

برای آشنایی با نحوه عملکرد Reflex [صفحه معماری](https://reflex.dev/blog/2024-03-21-reflex-architecture/#the-reflex-architecture) را ببینید.

## ⚙️ Installation - نصب و راه اندازی

یک ترمینال را باز کنید و اجرا کنید (نیازمند Python 3.9+):

```bash
pip install reflex
```

## 🥳 اولین برنامه خود را ایجاد کنید

نصب `reflex` همچنین `reflex` در خط فرمان را نصب میکند.

با ایجاد یک پروژه جدید موفقیت آمیز بودن نصب را تست کنید. (`my_app_name` را با اسم پروژه خودتان جایگزین کنید):

```bash
mkdir my_app_name
cd my_app_name
reflex init
```

این دستور یک برنامه الگو(تمپلیت) را در فهرست(دایرکتوری) جدید شما مقداردهی اولیه می کند

می توانید این برنامه را در حالت توسعه(development) اجرا کنید:

```bash
reflex run
```

باید برنامه خود را در حال اجرا ببینید در http://localhost:3000.

اکنون می‌توانید کد منبع را در «my_app_name/my_app_name.py» تغییر دهید. Reflex دارای تازه‌سازی‌های سریعی است، بنابراین می‌توانید تغییرات خود را بلافاصله پس از ذخیره کد خود مشاهده کنید.


## 🫧 Example App - برنامه نمونه

بیایید یک مثال بزنیم: ایجاد یک رابط کاربری برای تولید تصویر [DALL·E](https://platform.openai.com/docs/guides/images/image-generation?context=node). برای سادگی، ما فراخوانی میکنیم [OpenAI API](https://platform.openai.com/docs/api-reference/authentication), اما می توانید آن را با یک مدل ML که به صورت محلی اجرا می شود جایگزین کنید.

&nbsp;

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/dalle.gif" alt="A frontend wrapper for DALL·E, shown in the process of generating an image." width="550" />
</div>

&nbsp;

در اینجا کد کامل برای ایجاد این پروژه آمده است. همه اینها در یک فایل پایتون انجام می شود!


  
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





## بیاید سادش کنیم

<div align="center">
<img src="docs/images/dalle_colored_code_example.png" alt="Explaining the differences between backend and frontend parts of the DALL-E app." width="900" />
</div>


### **Reflex UI - رابط کاربری رفلکس** 

بیایید با رابط کاربری شروع کنیم.

```python
def index():
    return rx.center(
        ...
    )
```

تابع `index` قسمت فرانت اند برنامه را تعریف می کند.

ما از اجزای مختلفی مثل `center`, `vstack`, `input` و `button` استفاده میکنیم تا فرانت اند را بسازیم. اجزاء را می توان درون یکدیگر قرار داد
برای ایجاد طرح بندی های پیچیده می توانید از args کلمات کلیدی برای استایل دادن به آنها از CSS استفاده کنید.

رفلکس دارای [بیش از 60  جزء](https://reflex.dev/docs/library) برای کمک به شما برای شروع. ما به طور فعال اجزای بیشتری را اضافه می کنیم, و این خیلی آسان است که [اجزا خود را بسازید](https://reflex.dev/docs/wrapping-react/overview/).

### **State - حالت**

رفلکس رابط کاربری شما را به عنوان تابعی از وضعیت شما نشان می دهد.

```python
class State(rx.State):
    """The app state."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False

```

حالت تمام متغیرها(variables) (به نام vars) را در یک برنامه که می توانند تغییر دهند و توابعی که آنها را تغییر می دهند تعریف می کند..

در اینجا حالت از یک `prompt` و `image_url` تشکیل شده است. همچنین دو بولی `processing` و `complete` برای نشان دادن زمان غیرفعال کردن دکمه (در طول تولید تصویر) و زمان نمایش تصویر نتیجه وجود دارد.

### **Event Handlers - کنترل کنندگان رویداد**

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

در داخل حالت، توابعی به نام کنترل کننده رویداد تعریف می کنیم که متغیرهای حالت را تغییر می دهند. کنترل کننده های رویداد راهی هستند که می توانیم وضعیت را در Reflex تغییر دهیم. آنها را می توان در پاسخ به اقدامات کاربر، مانند کلیک کردن روی یک دکمه یا تایپ کردن در یک متن، فراخوانی کرد. به این اعمال وقایع می گویند.

برنامه DALL·E ما دارای یک کنترل کننده رویداد، `get_image` است که این تصویر را از OpenAI API دریافت می کند. استفاده از `yield` در وسط کنترل‌کننده رویداد باعث به‌روزرسانی رابط کاربری می‌شود. در غیر این صورت رابط کاربری در پایان کنترل کننده رویداد به روز می شود.

### **Routing - مسیریابی**

بالاخره اپلیکیشن خود را تعریف می کنیم.

```python
app = rx.App()
```

ما یک صفحه از root برنامه را به جزء index اضافه می کنیم. ما همچنین عنوانی را اضافه می کنیم که در برگه پیش نمایش/مرورگر صفحه نمایش داده می شود.

```python
app.add_page(index, title="DALL-E")
```

با افزودن صفحات بیشتر می توانید یک برنامه چند صفحه ای ایجاد کنید.

## 📑 Resources - منابع

<div align="center">

📑 [اسناد](https://reflex.dev/docs/getting-started/introduction) &nbsp; |  &nbsp; 🗞️ [وبلاگ](https://reflex.dev/blog) &nbsp; |  &nbsp; 📱 [کتابخانه جزء](https://reflex.dev/docs/library) &nbsp; |  &nbsp; 🖼️ [گالری](https://reflex.dev/docs/gallery) &nbsp; |  &nbsp; 🛸 [استقرار](https://reflex.dev/docs/hosting/deploy-quick-start)  &nbsp;   

</div>


## ✅ Status - وضعیت

رفلکس(reflex) در دسامبر 2022 با نام Pynecone راه اندازی شد.

از فوریه 2024، سرویس میزبانی ما در آلفا است! در این مدت هر کسی می‌تواند برنامه‌های خود را به صورت رایگان اجرا کند. [نقشه راه](https://github.com/reflex-dev/reflex/issues/2727) را ببینید تا متوجه شوید چه برنامه‌ریزی شده است.

رفلکس(reflex) هر هفته نسخه ها و ویژگی های جدیدی دارد! مطمئن شوید که :star: ستاره و  :eyes: این مخزن را تماشا کنید تا به روز بمانید.

## Contributing - مشارکت کردن

ما از مشارکت در هر اندازه استقبال می کنیم! در زیر چند راه خوب برای شروع در انجمن رفلکس آورده شده است.

-   **به Discord ما بپیوندید**: [Discord](https://discord.gg/T5WSbC2YtQ) ما بهترین مکان برای دریافت کمک در مورد پروژه Reflex و بحث در مورد اینکه چگونه می توانید کمک کنید است.
-   **بحث های GitHub**: راهی عالی برای صحبت در مورد ویژگی هایی که می خواهید اضافه کنید یا چیزهایی که گیج کننده هستند/نیاز به توضیح دارند.
-   **قسمت مشکلات GitHub**: [قسمت مشکلات](https://github.com/reflex-dev/reflex/issues) یک راه عالی برای گزارش اشکال هستند. علاوه بر این، می توانید یک مشکل موجود را حل کنید و یک PR(pull request) ارسال کنید.

ما فعالانه به دنبال مشارکت کنندگان هستیم، فارغ از سطح مهارت یا تجربه شما. برای مشارکت  [CONTIBUTING.md](https://github.com/reflex-dev/reflex/blob/main/CONTRIBUTING.md) را بررسی کنید.


## All Thanks To Our Contributors - با تشکر از همکاران ما:
<a href="https://github.com/reflex-dev/reflex/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=reflex-dev/reflex" />
</a>

## License - مجوز

رفلکس متن باز و تحت مجوز [Apache License 2.0](LICENSE) است.
