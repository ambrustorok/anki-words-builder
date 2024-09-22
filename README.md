# Danish-English Language Learning App

A simple app for learners to generate Danish-English vocabulary flashcards, including translations, word forms, and pronunciations. The app integrates with Anki to export custom decks and supports text and audio-based learning. Built using Gradio and OpenAI's API, this tool helps streamline vocabulary building through an intuitive interface.

## Features
- Generate vocabulary lists with translations
- Automatically fetch word forms and pronunciations
- Export to Anki-ready flashcard decks (supports `.apkg` format)
- Simple user interface for practicing Danish-English vocabulary
- Utilizes `ffmpeg` for audio processing

## Requirements

To install the necessary dependencies, ensure you have Python installed and run the following:

```bash
sudo apt install ffmpeg
pip install -r requirements.txt
```