<div align="center">
<img src="/docs/images/reflex.svg" alt="Reflex Logo" width="300px">
<hr>

### **✨ Ứng dụng web hiệu suất cao, tùy chỉnh bằng Python thuần. Deploy trong vài giây. ✨**

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

Reflex là một thư viện để xây dựng ứng dụng web toàn bộ bằng Python thuần.

Các tính năng chính:

- **Python thuần tuý** - Viết toàn bộ ứng dụng cả backend và frontend hoàn toàn bằng Python, không cần học JavaScript.
- **Full Flexibility** - Reflex dễ dàng để bắt đầu, nhưng cũng có thể mở rộng lên các ứng dụng phức tạp.
- **Deploy Instantly** - Sau khi xây dựng ứng dụng, bạn có thể triển khai bằng [một dòng lệnh](https://reflex.dev/docs/hosting/deploy-quick-start/) hoặc triển khai trên server của riêng bạn.

Đọc [bài viết về kiến trúc hệ thống](https://reflex.dev/blog/2024-03-21-reflex-architecture/#the-reflex-architecture) để hiểu rõ các hoạt động của Reflex.

## ⚙️ Cài đặt

Mở cửa sổ lệnh và chạy (Yêu cầu Python phiên bản 3.10+):

```bash
pip install reflex
```

## 🥳 Tạo ứng dụng đầu tiên

Cài đặt `reflex` cũng như cài đặt công cụ dòng lệnh `reflex`.

Kiểm tra việc cài đặt đã thành công hay chưa bằng cách tạo mới một ứng dụng. (Thay `my_app_name` bằng tên ứng dụng của bạn):

```bash
mkdir my_app_name
cd my_app_name
reflex init
```

Lệnh này tạo ra một ứng dụng mẫu trong một thư mục mới.

Bạn có thể chạy ứng dụng ở chế độ phát triển.

```bash
reflex run
```

Bạn có thể xem ứng dụng của bạn ở địa chỉ http://localhost:3000.

Bạn có thể thay đổi mã nguồn ở `my_app_name/my_app_name.py`. Reflex nhanh chóng làm mới và bạn có thể thấy thay đổi trên ứng dụng của bạn ngay lập tức khi bạn lưu file.

## 🫧 Ứng dụng ví dụ

Bắt đầu với ví dụ: tạo một ứng dụng tạo ảnh bằng [DALL·E](https://platform.openai.com/docs/guides/images/image-generation?context=node). Để cho đơn giản, chúng ta sẽ sử dụng [OpenAI API](https://platform.openai.com/docs/api-reference/authentication), nhưng bạn có thể sử dụng model của chính bạn được triển khai trên local.

&nbsp;

<div align="center">
<img src="/docs/images/dalle.gif" alt="A frontend wrapper for DALL·E, shown in the process of generating an image." width="550" />
</div>

&nbsp;

Đây là toàn bộ đoạn mã để xây dựng ứng dụng trên. Nó được viết hoàn toàn trong một file Python!

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

## Hãy phân tích chi tiết.

<div align="center">
<img src="/docs/images/dalle_colored_code_example.png" alt="Explaining the differences between backend and frontend parts of the DALL-E app." width="900" />
</div>

### **Reflex UI**

Bắt đầu với giao diện chính.

```python
def index():
    return rx.center(
        ...
    )
```

Hàm `index` định nghĩa phần giao diện chính của ứng dụng.

Chúng tôi sử dụng các component (thành phần) khác nhau như `center`, `vstack`, `input` và `button` để xây dựng giao diện phía trước.
Các component có thể được lồng vào nhau để tạo ra các bố cục phức tạp. Và bạn cũng có thể sử dụng từ khoá `args` để tận dụng đầy đủ sức mạnh của CSS.

Reflex có đến hơn [60 component được xây dựng sẵn](https://reflex.dev/docs/library) để giúp bạn bắt đầu. Chúng ta có thể tạo ra một component mới khá dễ dàng, thao khảo: [xây dựng component của riêng bạn](https://reflex.dev/docs/wrapping-react/overview/).

### **State**

Reflex biểu diễn giao diện bằng các hàm của state (trạng thái).

```python
class State(rx.State):
    """The app state."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False

```

Một state định nghĩa các biến (được gọi là vars) có thể thay đổi trong một ứng dụng và cho phép các hàm có thể thay đổi chúng.

Tại đây state được cấu thành từ một `prompt` và `image_url`.
Có cũng những biến boolean `processing` và `complete`
để chỉ ra khi nào tắt nút (trong quá trình tạo hình ảnh)
và khi nào hiển thị hình ảnh kết quả.

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

Với các state, chúng ta định nghĩa các hàm có thể thay đổi state vars được gọi là event handlers. Event handler là cách chúng ta có thể thay đổi state trong Reflex. Chúng có thể là phản hồi khi người dùng thao tác, chằng hạn khi nhấn vào nút hoặc khi đang nhập trong text box. Các hành động này được gọi là event.

Ứng dụng DALL·E. của chúng ta có một event handler, `get_image` để lấy hình ảnh từ OpenAI API. Sử dụng từ khoá `yield` in ở giữa event handler để cập nhật giao diện. Hoặc giao diện có thể cập nhật ở cuối event handler.

### **Routing**

Cuối cùng, chúng ta định nghĩa một ứng dụng.

```python
app = rx.App()
```

Chúng ta thêm một trang ở đầu ứng dụng bằng index component. Chúng ta cũng thêm tiêu đề của ứng dụng để hiển thị lên trình duyệt.

```python
app.add_page(index, title="DALL-E")
```

Bạn có thể tạo một ứng dụng nhiều trang bằng cách thêm trang.

## 📑 Tài liệu

<div align="center">

📑 [Docs](https://reflex.dev/docs/getting-started/introduction) &nbsp; | &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; | &nbsp; 📱 [Component Library](https://reflex.dev/docs/library) &nbsp; | &nbsp; 🖼️ [Templates](https://reflex.dev/templates/) &nbsp; | &nbsp; 🛸 [Deployment](https://reflex.dev/docs/hosting/deploy-quick-start) &nbsp;

</div>

## ✅ Status

Reflex phát hành vào tháng 12/2022 với tên là Pynecone.

Từ năm 2025, [Reflex Cloud](https://cloud.reflex.dev) đã ra mắt để cung cấp trải nghiệm lưu trữ tốt nhất cho các ứng dụng Reflex. Chúng tôi sẽ tiếp tục phát triển và triển khai thêm nhiều tính năng mới.

Reflex ra phiên bản mới với các tính năng mới hàng tuần! Hãy :star: star và :eyes: watch repo này để thấy các cập nhật mới nhất.

## Contributing

Chúng tôi chào đón mọi đóng góp dù lớn hay nhỏ. Dưới đây là các cách để bắt đầu với cộng đồng Reflex.

- **Discord**: [Discord](https://discord.gg/T5WSbC2YtQ) của chúng tôi là nơi tốt nhất để nhờ sự giúp đỡ và thảo luận các bạn có thể đóng góp.
- **GitHub Discussions**: Là cách tốt nhất để thảo luận về các tính năng mà bạn có thể đóng góp hoặc những điều bạn chưa rõ.
- **GitHub Issues**: [Issues](https://github.com/reflex-dev/reflex/issues) là nơi tốt nhất để thông báo. Ngoài ra bạn có thể sửa chữa các vấn đề bằng cách tạo PR.

Chúng tôi luôn sẵn sàng tìm kiếm các contributor, bất kể kinh nghiệm. Để tham gia đóng góp, xin mời xem
[CONTRIBUTING.md](https://github.com/reflex-dev/reflex/blob/main/CONTRIBUTING.md)

## Xin cảm ơn các Contributors:

<a href="https://github.com/reflex-dev/reflex/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=reflex-dev/reflex" />
</a>

## License

Reflex là mã nguồn mở và sử dụng giấy phép [Apache License 2.0](/LICENSE).
