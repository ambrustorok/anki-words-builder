# Anki Words Builder
Anki Words Builder is a tool designed to help you create and manage vocabulary decks for [Anki](https://apps.ankiweb.net/), a popular flashcard application. This tool simplifies the process of building and organizing your vocabulary lists, making it easier to study and retain new words.

## Features

- **Easy Vocabulary Management**: Add, edit, and delete words and their definitions.
- **Deck Export**: Export your vocabulary lists to Anki-compatible formats.
- **Customizable**: Customize the fields and formats according to your needs.
- **User-Friendly Interface**: Simple and intuitive interface for efficient workflow.

## Installation

To install Anki Words Builder, follow these steps:

1. **Clone the Repository**:
    ```bash
    git clone https://github.com/ambrustorok/anki-words-builder.git
    cd anki-words-builder
    ```

2. **Set Up the Environment File**:
    Create a `.env` file in the root directory and add the necessary environment variables:
    ```plaintext
    OPENAI_API_KEY=your_openai_api_key
    ```

3. Install [uv](https://docs.astral.sh/uv/#getting-started) if you haven't already:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

3. **Install Dependencies**:
    ```bash
    uv pip sync requirements.txt
    ```

4. **Run the Application**:
    ```bash
    uv run src/app.py
    ```

## Usage

1. **Add Words**: Use the interface to add new words and their definitions.
2. **Edit Words**: Modify existing words and their definitions as needed.
3. **Delete Words**: Remove words that you no longer need.
4. **Export Deck**: Export your vocabulary list to an Anki-compatible format.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Background

This project started as a side project for me to learn Danish. I wanted a tool that could help me efficiently manage and study new vocabulary, and Anki Words Builder was the result.
