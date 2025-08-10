<div align="center">
<img src="/docs/images/reflex.svg" alt="Reflex Logo" width="300px">
<hr>

### **✨ Saf Python'da performanslı, özelleştirilebilir web uygulamaları. Saniyeler içinde dağıtın. ✨**

[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![versions](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentation](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![PyPI Downloads](https://static.pepy.tech/badge/reflex)](https://pepy.tech/projects/reflex)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)

</div>

---

[English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md) | [Türkçe](https://github.com/reflex-dev/reflex/blob/main/docs/tr/README.md) | [हिंदी](https://github.com/reflex-dev/reflex/blob/main/docs/in/README.md) | [Português (Brasil)](https://github.com/reflex-dev/reflex/blob/main/docs/pt/pt_br/README.md) | [Italiano](https://github.com/reflex-dev/reflex/blob/main/docs/it/README.md) | [Español](https://github.com/reflex-dev/reflex/blob/main/docs/es/README.md) | [한국어](https://github.com/reflex-dev/reflex/blob/main/docs/kr/README.md) | [日本語](https://github.com/reflex-dev/reflex/blob/main/docs/ja/README.md) | [Deutsch](https://github.com/reflex-dev/reflex/blob/main/docs/de/README.md) | [Persian (پارسی)](https://github.com/reflex-dev/reflex/blob/main/docs/pe/README.md) | [Tiếng Việt](https://github.com/reflex-dev/reflex/blob/main/docs/vi/README.md)

---

# Reflex

Reflex, saf Python'da tam yığın web uygulamaları oluşturmak için bir kütüphanedir.

Temel özellikler:

- **Saf Python** - Uygulamanızın ön uç ve arka uç kısımlarının tamamını Python'da yazın, Javascript öğrenmenize gerek yok.
- **Tam Esneklik** - Reflex ile başlamak kolaydır, ancak karmaşık uygulamalara da ölçeklenebilir.
- **Anında Dağıtım** - Oluşturduktan sonra, uygulamanızı [tek bir komutla](https://reflex.dev/docs/hosting/deploy-quick-start/) dağıtın veya kendi sunucunuzda barındırın.

Reflex'in perde arkasında nasıl çalıştığını öğrenmek için [mimari sayfamıza](https://reflex.dev/blog/2024-03-21-reflex-architecture/#the-reflex-architecture) göz atın.

## ⚙️ Kurulum

Bir terminal açın ve çalıştırın (Python 3.10+ gerekir):

```bash
pip install reflex
```

## 🥳 İlk Uygulamanı Oluştur

`reflex`'i kurduğunuzda `reflex` komut satırı aracınıda kurmuş olursunuz.

Kurulumun başarılı olduğunu test etmek için yeni bir proje oluşturun. (`my_app_name`'i proje ismiyle değiştirin.):

```bash
mkdir my_app_name
cd my_app_name
reflex init
```

Bu komut ile birlikte yeni oluşturduğunuz dizinde bir şablon uygulaması oluşturur.

Uygulamanızı geliştirme modunda başlatabilirsiniz:

```bash
reflex run
```

Uygulamanızın http://localhost:3000 adresinde çalıştığını görmelisiniz.

Şimdi `my_app_name/my_app_name.py` yolundaki kaynak kodu düzenleyebilirsiniz. Reflex'in hızlı yenileme özelliği vardır, böylece kodunuzu kaydettiğinizde değişikliklerinizi anında görebilirsiniz.

## 🫧 Örnek Uygulama

Bir örnek üzerinden gidelim: [DALL·E](https://platform.openai.com/docs/guides/images/image-generation?context=node) kullanarak bir görüntü oluşturma arayüzü oluşturalım. Basit olması açısından, yalnızca [OpenAI API](https://platform.openai.com/docs/api-reference/authentication)'ını kullanıyoruz, ancak bunu yerel olarak çalıştırılan bir ML modeliyle değiştirebilirsiniz.

&nbsp;

<div align="center">
<img src="/docs/images/dalle.gif" alt="A frontend wrapper for DALL·E, shown in the process of generating an image." width="550" />
</div>

&nbsp;

İşte bunu oluşturmak için kodun tamamı. Her şey sadece bir Python dosyasıyla hazırlandı!

```python
import reflex as rx
import openai

openai_client = openai.OpenAI()


class State(rx.State):
    """Uygulama durumu."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False

    def get_image(self):
        """Prompt'tan görüntüyü alın."""
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

# Sayfa ve durumu uygulamaya ekleyin.
app = rx.App()
app.add_page(index, title="Reflex:DALL-E")
```

## Daha Detaylı İceleyelim

<div align="center">
<img src="/docs/images/dalle_colored_code_example.png" alt="DALL-E uygulamasının arka uç ve ön uç kısımları arasındaki farkları açıklama." width="900" />
</div>

### **Reflex UI**

UI (Kullanıcı Arayüzü) ile başlayalım.

```python
def index():
    return rx.center(
        ...
    )
```

Bu `index` fonkisyonu uygulamanın frontend'ini tanımlar.

Frontend'i oluşturmak için `center`, `vstack`, `input`, ve `button` gibi farklı bileşenler kullanıyoruz. Karmaşık düzenler oluşturmak için bileşenleri birbirinin içine yerleştirilebiliriz. Ayrıca bunları CSS'nin tüm gücüyle şekillendirmek için anahtar kelime argümanları kullanabilirsiniz.

Reflex, işinizi kolaylaştırmak için [60'tan fazla dahili bileşen](https://reflex.dev/docs/library) içerir. Aktif olarak yeni bileşen ekliyoruz ve [kendi bileşenlerinizi oluşturmak](https://reflex.dev/docs/wrapping-react/overview/) oldukça kolay.

### **Durum (State)**

Reflex arayüzünüzü durumunuzun bir fonksiyonu olarak temsil eder.

```python
class State(rx.State):
    """Uygulama durumu."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False
```

Durum (State), bir uygulamadaki değişebilen tüm değişkenleri (vars olarak adlandırılır) ve bunları değiştiren fonksiyonları tanımlar.

Burada durum `prompt` ve `image_url`inden oluşur. Ayrıca düğmenin ne zaman devre dışı bırakılacağını (görüntü oluşturma sırasında) ve görüntünün ne zaman gösterileceğini belirtmek için `processing` ve `complete` booleanları da vardır.

### **Olay İşleyicileri (Event Handlers)**

```python
def get_image(self):
    """Prompt'tan görüntüyü alın."""
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

Durum içinde, durum değişkenlerini değiştiren olay işleyicileri adı verilen fonksiyonları tanımlarız. Olay işleyicileri, Reflex'te durumu değiştirebilmemizi sağlar. Bir düğmeye tıklamak veya bir metin kutusuna yazı yazmak gibi kullanıcı eylemlerine yanıt olarak çağrılabilirler. Bu eylemlere olay denir.

DALL·E uygulamamız OpenAI API'ından bu görüntüyü almak için `get_image` adlı bir olay işleyicisine sahiptir. Bir olay işleyicisinin ortasında `yield`ın kullanılması UI'ın güncellenmesini sağlar. Aksi takdirde UI olay işleyicisinin sonunda güncellenecektir.

### **Yönlendirme (Routing)**

En sonunda uygulamamızı tanımlıyoruz.

```python
app = rx.App()
```

Uygulamamızın kök dizinine index bileşeninden bir sayfa ekliyoruz. Ayrıca sayfa önizlemesinde/tarayıcı sekmesinde görünecek bir başlık ekliyoruz.

```python
app.add_page(index, title="DALL-E")
```

Daha fazla sayfa ekleyerek çok sayfalı bir uygulama oluşturabilirsiniz.

## 📑 Kaynaklar

<div align="center">

📑 [Docs](https://reflex.dev/docs/getting-started/introduction) &nbsp; | &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; | &nbsp; 📱 [Component Library](https://reflex.dev/docs/library) &nbsp; | &nbsp; 🖼️ [Templates](https://reflex.dev/templates/) &nbsp; | &nbsp; 🛸 [Deployment](https://reflex.dev/docs/hosting/deploy-quick-start) &nbsp;

</div>

## ✅ Durum

Reflex, Aralık 2022'de Pynecone adıyla piyasaya sürüldü.

2025'in başından itibaren, Reflex uygulamaları için en iyi barındırma deneyimini sunmak amacıyla [Reflex Cloud](https://cloud.reflex.dev) hizmete girmiştir. Bunu geliştirmeye ve daha fazla özellik eklemeye devam edeceğiz.

Reflex'in her hafta yeni sürümleri ve özellikleri geliyor! Güncel kalmak için bu depoyu :star: yıldızlamayı ve :eyes: izlediğinizden emin olun.

## Katkı

Her boyuttaki katkıları memnuniyetle karşılıyoruz! Aşağıda Reflex topluluğuna adım atmanın bazı yolları mevcut.

- **Discord Kanalımıza Katılın**: [Discord'umuz](https://discord.gg/T5WSbC2YtQ), Reflex projeniz hakkında yardım almak ve nasıl katkıda bulunabileceğinizi tartışmak için en iyi yerdir.
- **GitHub Discussions**: Eklemek istediğiniz özellikler veya kafa karıştırıcı, açıklığa kavuşturulması gereken şeyler hakkında konuşmanın harika bir yolu.
- **GitHub Issues**: [Issues](https://github.com/reflex-dev/reflex/issues) hataları bildirmenin mükemmel bir yoludur. Ayrıca mevcut bir sorunu deneyip çözebilir ve bir PR (Pull Requests) gönderebilirsiniz.

Beceri düzeyiniz veya deneyiminiz ne olursa olsun aktif olarak katkıda bulunacak kişiler arıyoruz. Katkı sağlamak için katkı sağlama rehberimize bakabilirsiniz: [CONTRIBUTING.md](https://github.com/reflex-dev/reflex/blob/main/CONTRIBUTING.md)

## Hepsi Katkıda Bulunanlar Sayesinde:

<a href="https://github.com/reflex-dev/reflex/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=reflex-dev/reflex" />
</a>

## Lisans

Reflex açık kaynaklıdır ve [Apache License 2.0](/LICENSE) altında lisanslıdır.
