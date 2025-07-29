# GCodeMaker v1.0

**shopfloor.works** – A standalone, offline-first G‑Code editor and annotator for CNC programmers.

## Description

GCodeMaker is a cross‑platform desktop application built with Python and PyQt5. It provides:

* **Syntax Highlighting** for G‑Code commands, coordinates, and parameters.
* **Side‑by‑Side Annotation Pane** that decodes each line of G‑Code into human‑readable descriptions.
* **Dictionary/Macros Widget** for quickly inserting code snippets and reusable G‑Code macros.
* **Profile Support** to manage different machine configurations (annotations & dictionaries per profile).
* **Offline‑First Design** – no internet connection required, ideal for secure or air‑gapped environments.

## Features

* **Rich G‑Code Highlighter**: Colors G, M, T, F, S, X, Y, Z, I/J/K, R/Q/N, C (chamfer), P (dwell) tokens with customizable QSS styling.
* **Annotation Engine**: Parses each token against a profile‑specific annotations JSON to provide real‑time explanations.
* **Dictionary Widget**: Search, add, edit, and double‑click to insert predefined code snippets (e.g., tool changes, canned cycles).
* **Profile Management**: Create, rename, or delete machine profiles, each with independent annotation and dictionary sets.
* **Keyboard Shortcuts**: Standard Ctrl+S to save, context menus for dictionary entries.
* **Styling via QSS**: UI theming supported through `style.qss` – tweak colors, padding, and fonts without touching code.

## Requirements

* Python **3.7+**
* PyQt5

## Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/GCodeMaker.git
   cd GCodeMaker
   ```
2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```
3. **Run the application**

   ```bash
   python main.py
   ```

> The app will automatically create a `profiles/` folder on first run with a default profile.

## Usage

1. **Editor Pane** (left): Write or load a `.gcode`/`.nc` file.
2. **Annotation Pane** (center): View parsed explanations of each G‑Code line.
3. **Dictionary Pane** (right): Switch profiles, search or add new macros, double‑click to insert.
4. **Profile Combo‑Box** (toolbar): Switch between machine profiles. Profiles control which annotation and dictionary files are loaded (`profiles/<name>-annotations.json`, `profiles/<name>-dictionary.json`).
5. **Toolbar Buttons**:

   * New: Clear the editor
   * Open: Load existing G‑Code file
   * Save / Save As: Write `.gcode` file to disk

## Configuration & Styling

* **Annotations & Dictionary** files live in the `profiles/` directory.
* **QSS Stylesheet** (`style.qss`) controls widget colors, borders, and typography. Modify it to customize the look and feel.
* **Icons**: The window icon is `green_g_icon.png` (replace to rebrand).


## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-new-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/my-new-feature`)
5. Open a Pull Request

Please follow the existing code style and include tests where applicable.

## License

This project is licensed under the MIT License. See \[LICENSE]\(MIT\ License.txt) for details.

---

*Built with ♥ by Micah Foster.*
