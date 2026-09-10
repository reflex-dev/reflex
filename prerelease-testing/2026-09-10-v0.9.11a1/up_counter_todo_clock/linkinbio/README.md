# Link in Bio App
This application is built using Reflex.dev, a powerful framework for creating interactive web applications using pure Python. This app allows you to showcase your online presence with a customizable link in bio page.

## Features

- **Customizable Links**: Easily add links to your personal website, Twitter, GitHub, LinkedIn, and more.
- **Responsive Design**: The app is designed to look great on both desktop and mobile devices.
- **Stylish UI**: Uses a vibrant gradient background and modern UI components.

## Installation

To get started with this project follow these steps:

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

### Steps

1. **Clone the Repository**

   Clone the repository to your local machine using the following command:

      ```bash
   git clone https://github.com/reflex-dev/reflex-examples
   cd reflex-examples/linkinbio
   ```
2. **Install Dependencies**

   Install the required Python packages using pip:

   ```bash
   pip install -r requirements.txt
   ```

      The `requirements.txt` file specifies the necessary Reflex version:
   ```plaintext:linkinbio/requirements.txt
   startLine: 1
   endLine: 2
   ```



3. **Run the Application**

   Start the application using the following command:
   ```bash
   reflex run
   ```

   The app will be accessible at `http://localhost:3000` by default.

## Project Structure

- **linkinbio.py**: Contains the main application logic, including the `link_button` and `index` functions.
  ```python:linkinbio/linkinbio/linkinbio.py
  startLine: 1
  endLine: 57
  ```

- **style.py**: Defines the styling for the app components, including buttons, links, and layout.
  ```python:linkinbio/linkinbio/style.py
  startLine: 1
  endLine: 55
  ```

- **rxconfig.py**: Configuration file for the Reflex app.
  ```python:linkinbio/rxconfig.py
  startLine: 1
  endLine: 5
  ```

- **.gitignore**: Specifies files and directories to be ignored by Git.
  ```plaintext:linkinbio/.gitignore
  startLine: 1
  endLine: 6
  ```

## Customization

You can customize the links and personal information by editing the `index` function in `linkinbio.py`. Update the `name`, `bio`, `avatar_url`, and `links` list to reflect your personal details.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request for any improvements or bug fixes.

## Contact

This template was created by @erinmikailstaples (https://github.com/erinmikailstaples). Feel free to reach out for any questions, feedback, or collaboration opportunities. 