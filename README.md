# Doremi

<p align="center">
  <img src="assets/logo.png" alt="Doremi logo" width="220" />
</p>

<p align="center">
  <strong>Reproductor de música local + cliente de streaming para Linux</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white" alt="Python version" />
  <img src="https://img.shields.io/badge/Qt-PySide6-41CD52?logo=qt&logoColor=white" alt="Qt PySide6" />
  <img src="https://img.shields.io/badge/Rust-Native-000000?logo=rust&logoColor=white" alt="Rust native module" />
</p>

Doremi es un reproductor musical moderno para escritorio, pensado para ofrecer una experiencia elegante, rápida y centrada en el usuario en Linux. Combina reproducción local, biblioteca personal, streaming desde YouTube Music y una interfaz basada en Qt/QML con una capa nativa en Rust para optimizar tareas intensivas como procesamiento visual y variantes de color.

## Características principales

- Reproducción local y gestión de biblioteca
- Integración con YouTube Music para streaming y descubrimiento
- Interfaz moderna con QML y tema dinámico
- Módulo nativo en Rust para rendimiento y procesamiento visual
- Descargas, historial, listas de reproducción y estadísticas
- Soporte para integración del sistema: bandeja, MPRIS, Discord, Last.fm y atajos
- Diseño preparado para Linux con foco en fluidez y estética premium

## Stack tecnológico

- Python 3.12 / 3.13
- PySide6 + QML
- SQLAlchemy + SQLite
- VLC / python-vlc
- Rust + PyO3 + maturin
- YouTube Music client + yt-dlp

## Requisitos

- Python 3.12 o 3.13
- Qt / PySide6
- VLC instalado en el sistema
- Rust y maturin para compilar el módulo nativo

> Python 3.14 queda excluido temporalmente por compatibilidad con dependencias del proyecto.

## Instalación

```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]" maturin
```

## Módulo nativo Rust

El proyecto requiere compilar el módulo nativo antes de ejecutar la aplicación.

```bash
cd src/doremi/native_rs
maturin develop --release
```

## Ejecución

```bash
doremi
# o
PYTHONPATH=src python -m doremi.main
```

## Tests

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m pytest tests/ -q
```

## Estado del proyecto

Este repositorio representa la evolución del proyecto hacia una arquitectura más moderna con Rust + QML como base de rendimiento y experiencia visual, manteniendo compatibilidad con la base Python existente.

## Licencia

Este proyecto se distribuye bajo la licencia incluida en [LICENSE](LICENSE).

---

Desarrollado con ❤️ por Eirom.
