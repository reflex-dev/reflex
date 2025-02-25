
<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg#gh-light-mode-only" alt="Reflex लोगो" width="300px">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg#gh-dark-mode-only" alt="Reflex लोगो" width="300px">

<hr>

### **✨ प्रदर्शनकारी, अनुकूलित वेब ऐप्स, शुद्ध Python में। सेकंडों में तैनात करें। ✨**

[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![versions](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentaiton](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)

</div>

---

## [English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md) | [Türkçe](https://github.com/reflex-dev/reflex/blob/main/docs/tr/README.md) | [हिंदी](https://github.com/reflex-dev/reflex/blob/main/docs/in/README.md) | [한국어](https://github.com/reflex-dev/reflex/blob/main/docs/kr/README.md) | [日本語](https://github.com/reflex-dev/reflex/blob/main/docs/ja/README.md) | [Deutsch](https://github.com/reflex-dev/reflex/blob/main/docs/de/README.md) | [Persian (پارسی)](https://github.com/reflex-dev/reflex/blob/main/docs/pe/README.md)

# Reflex

Reflex शुद्ध पायथन में पूर्ण-स्टैक वेब ऐप्स बनाने के लिए एक लाइब्रेरी है।

मुख्य विशेषताएँ:

- **शुद्ध पायथन** - अपने ऐप के फ्रंटएंड और बैकएंड को पायथन में लिखें, जावास्क्रिप्ट सीखने की जरूरत नहीं है।
- **पूर्ण लचीलापन** - Reflex के साथ शुरुआत करना आसान है, लेकिन यह जटिल ऐप्स के लिए भी स्केल कर सकता है।
- **तुरंत तैनाती** - बिल्डिंग के बाद, अपने ऐप को [एकल कमांड](https://reflex.dev/docs/hosting/deploy-quick-start/) के साथ तैनात करें या इसे अपने सर्वर पर होस्ट करें।

Reflex के अंदर के कामकाज को जानने के लिए हमारे [आर्किटेक्चर पेज](https://reflex.dev/blog/2024-03-21-reflex-architecture/#the-reflex-architecture) को देखें।

## ⚙️ इंस्टॉलेशन (Installation)

एक टर्मिनल खोलें और चलाएं (Python 3.10+ की आवश्यकता है):

```bash
pip install reflex
```

## 🥳 अपना पहला ऐप बनाएं (Create your first App)

reflex को इंस्टॉल करने से ही reflex कमांड लाइन टूल भी इंस्टॉल हो जाता है।

सुनिश्चित करें कि इंस्टॉलेशन सफल थी, एक नया प्रोजेक्ट बनाकर इसे टेस्ट करें। ('my_app_name' की जगह अपने प्रोजेक्ट का नाम रखें):

```bash
mkdir my_app_name
cd my_app_name
reflex init
```

यह कमांड आपकी नयी डायरेक्टरी में एक टेम्पलेट ऐप को प्रारंभ करता है।

आप इस ऐप को development मोड में चला सकते हैं:

```bash
reflex run
```

आपको http://localhost:3000 पर अपने ऐप को चलते हुए देखना चाहिए।

अब आप my_app_name/my_app_name.py में source कोड को संशोधित कर सकते हैं। Reflex में तेज रिफ्रेश की सुविधा है, इसलिए जब आप अपनी कोड को सहेजते हैं, तो आप अपने बदलावों को तुरंत देख सकते हैं।

## 🫧 उदाहरण ऐप (Example App)

एक उदाहरण पर चलते हैं: DALL·E से एक इमेज उत्पन्न करने के लिए UI। सरलता के लिए, हम सिर्फ OpenAI API को बुलाते हैं, लेकिन आप इसे ML मॉडल से बदल सकते हैं locally।

&nbsp;

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/dalle.gif" alt="DALL·E के लिए एक फ्रंटएंड रैपर, छवि उत्पन्न करने की प्रक्रिया में दिखाया गया।" width="550" />
</div>

&nbsp;

यहाँ पर इसका पूरा कोड है जिससे यह बनाया जा सकता है। यह सब एक ही Python फ़ाइल में किया गया है!

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

## इसे समझते हैं।

<div align="center">
<img src="https://github.com/reflex-dev/reflex/blob/main/docs/images/dalle_colored_code_example.png?raw=true" alt="DALL-E ऐप के बैकएंड और फ्रंटएंड भागों के बीच के अंतर की व्याख्या करता है।" width="900" />
</div>

### **Reflex UI**

हम UI के साथ शुरू करेंगे।

```python
def index():
    return rx.center(
        ...
    )
```

यह `index` फ़ंक्शन एप्लिकेशन की फ़्रंटएंड को परिभाषित करता है।

हम फ़्रंटएंड बनाने के लिए `center`, `vstack`, `input`, और `button` जैसे विभिन्न components का उपयोग करते हैं। Components को एक-दूसरे के भीतर डाल सकते हैं विस्तारित लेआउट बनाने के लिए। और आप CSS की पूरी ताक़त के साथ इन्हें स्टाइल करने के लिए कीवर्ड आर्ग्यूमेंट (keyword args) का उपयोग कर सकते हैं।

रिफ़्लेक्स के पास [60+ built-in components](https://reflex.dev/docs/library) हैं जो आपको शुरुआती मदद के लिए हैं। हम बहुत से components जोड़ रहे हैं, और अपने खुद के components बनाना भी आसान है। [create your own components](https://reflex.dev/docs/wrapping-react/overview/)

### **स्टेट (State)**

Reflex आपके UI को आपकी स्टेट (state) के एक फ़ंक्शन के रूप में प्रस्तुत करता है।

```python
class State(rx.State):
    """The app state."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False
```

स्टेट (state) ऐप में उन सभी वेरिएबल्स (vars) को परिभाषित करती है जो बदल सकती हैं और उन फ़ंक्शनों को जो उन्हें बदलते हैं।

यहां स्टेट (state) में `prompt` और `image_url` शामिल हैं। प्रगति और छवि दिखाने के लिए `processing` और `complete` बूलियन भी हैं।

### **इवेंट हैंडलर (Event Handlers)**

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

स्टेट (state) के अंदर, हम इवेंट हैंडलर्स (event handlers) को परिभाषित करते हैं जो स्टेट वेरिएबल्स को बदलते हैं। इवेंट हैंडलर्स (event handlers) से reflex में स्टेट (state) को मॉडिफ़ाय किया जा सकता हैं। इन्हें उपयोगकर्ता क्रियाओं (user actions) के प्रति प्रतिक्रिया (response) के रूप में बुलाया जा सकता है, जैसे कि बटन को क्लिक करना या टेक्स्ट बॉक्स में टाइप करना। इन क्रियाओं को इवेंट्स (events) कहा जाता है।

हमारे DALL·E. ऐप में एक इवेंट हैंडलर `get_image` है जिससे यह OpenAI API से इमेज प्राप्त करता है। इवेंट हैंडलर में `yield` का उपयोग करने कि वजह से UI अपडेट हो जाएगा। अन्यथा UI इवेंट हैंडलर के अंत में अपडेट होगा।

### **रूटिंग (Routing)**

आखिरकार, हम अपने एप्लिकेशन को परिभाषित करते हैं।

```python
app = rx.App()
```

हम अपने एप्लिकेशन के रूट से इंडेक्स कॉम्पोनेंट तक एक पेज को जोड़ते हैं। हम एक शीर्षक भी जोड़ते हैं जो पेज प्रीव्यू/ब्राउज़र टैब में दिखाई देगा।

```python
app.add_page(index, title="DALL-E")
```

आप और पेज जोड़कर एक मल्टी-पेज एप्लिकेशन बना सकते हैं।

## 📑 संसाधन (Resources)

<div align="center">

📑 [दस्तावेज़](https://reflex.dev/docs/getting-started/introduction) &nbsp; | &nbsp; 🗞️ [ब्लॉग](https://reflex.dev/blog) &nbsp; | &nbsp; 📱 [कॉम्पोनेंट लाइब्रेरी](https://reflex.dev/docs/library) &nbsp; | &nbsp; 🖼️ [गैलरी](https://reflex.dev/docs/gallery) &nbsp; | &nbsp; 🛸 [तैनाती](https://reflex.dev/docs/hosting/deploy) &nbsp;

</div>

## ✅ स्टेटस (Status)

Reflex दिसंबर 2022 में Pynecone नाम से शुरू हुआ।

फरवरी 2024 तक, हमारी होस्टिंग सेवा अल्फा में है! इस समय कोई भी अपने ऐप्स को मुफ्त में तैनात कर सकता है। देखें हमारी [रोडमैप](https://github.com/reflex-dev/reflex/issues/2727) योजनाबद्ध चीज़ों को जानने के लिए।

Reflex में हर सप्ताह नए रिलीज़ और फीचर्स आ रहे हैं! सुनिश्चित करें कि ⭐ स्टार और 👀 वॉच इस रेपोजिटरी को अपडेट रहने के लिए।

## (योगदान) Contributing

हम हर तरह के योगदान का स्वागत करते हैं! रिफ्लेक्स कम्यूनिटी में शुरुआत करने के कुछ अच्छे तरीके नीचे दिए गए हैं।

- **Join Our Discord** (डिस्कॉर्ड सर्वर से जुड़ें): Our [Discord](https://discord.gg/T5WSbC2YtQ) हमारा डिस्कॉर्ड रिफ्लेक्स प्रोजेक्ट पर सहायता प्राप्त करने और आप कैसे योगदान दे सकते हैं, इस पर चर्चा करने के लिए सबसे अच्छी जगह है।
- **GitHub Discussions** (गिटहब चर्चाएँ): उन सुविधाओं के बारे में बात करने का एक शानदार तरीका जिन्हें आप जोड़ना चाहते हैं या ऐसी चीज़ें जो भ्रमित करने वाली हैं/स्पष्टीकरण की आवश्यकता है।
- **GitHub Issues** (गिटहब समस्याएं): ये [बग](https://github.com/reflex-dev/reflex/issues) की रिपोर्ट करने का एक शानदार तरीका है। इसके अतिरिक्त, आप किसी मौजूदा समस्या को हल करने का प्रयास कर सकते हैं और एक पीआर सबमिट कर सकते हैं।

हम सक्रिय रूप से योगदानकर्ताओं की तलाश कर रहे हैं, चाहे आपका कौशल स्तर या अनुभव कुछ भी हो।योगदान करने के लिए [CONTRIBUTING.md](https://github.com/reflex-dev/reflex/blob/main/CONTRIBUTING.md) देखें।

## हमारे सभी योगदानकर्ताओं का धन्यवाद:

<a href="https://github.com/reflex-dev/reflex/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=reflex-dev/reflex" />
</a>

## लाइसेंस (License)

रिफ्लेक्स ओपन-सोर्स है और [अपाचे लाइसेंस 2.0](https://github.com/reflex-dev/reflex/blob/main/LICENSE) के तहत लाइसेंस प्राप्त है।
