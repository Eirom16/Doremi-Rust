# 🔥 Doremi: Tu Música, a Tu Manera 🎵

<p align="center">
  <img src="assets/logo.png" alt="Doremi Logo" width="250">
</p>

<p align="center">
  <b>Experimenta la música como nunca antes en tu escritorio Linux.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Estilo-Premium-ff4b2b?style=for-the-badge" alt="Premium Style">
  <img src="https://img.shields.io/badge/Velocidad-Increíble-ff9068?style=for-the-badge" alt="Fast">
  <img src="https://img.shields.io/badge/Para-Linux-00c6ff?style=for-the-badge" alt="Linux">
</p>

---

## 🌟 ¿Qué es Doremi?

**Doremi** no es solo un reproductor de música; es tu portal personal a todo el universo de
**La música en general**. Olvídate de las pestañas pesadas del navegador y disfruta de una aplicación dedicada, rápida y diseñada específicamente para integrarse con tu sistema Linux. 🐧✨

### ✨ Lo que te encantará:

- 🎧 **Streaming sin interrupciones**: Disfruta de toda tu biblioteca de YouTube Music con la mejor calidad de audio posible.
- 🎤 **Canta con nosotros**: Letras que se sincronizan con la música para que no pierdas ni una palabra.
- 🔥 **Sonido Perfecto**: Ajusta cada frecuencia con nuestro ecualizador de 10 bandas incorporado.
- 💾 **Tu música, siempre contigo**: Descarga tus canciones y álbumes favoritos para escucharlos incluso cuando no tengas internet.
- 🎮 **Presume tu gusto musical**: Integración automática con Discord para que todos vean qué joya estás escuchando.
- 📊 **Estadísticas Reales**: Conexión con Last.fm para que nunca pierdas el rastro de tus reproducciones.
- 🖱️ **Control Total**: Maneja todo desde la bandeja del sistema o con las teclas multimedia de tu teclado.

---

## 🚀 ¡Empieza a Escuchar Ahora!

¿Listo para subir el volumen? Sigue estos sencillos pasos:

> **Requisito de Python:** usa Python 3.12 o 3.13. Python 3.14 queda excluido temporalmente porque `aiosqlite` puede bloquearse al abrir conexiones SQLite en esa versión.

1.  **Abre la aplicación** y déjate llevar por la interfaz moderna.
2.  **Conecta tu cuenta** de forma segura para acceder a tus listas y recomendaciones.
3.  **Dale al Play** y disfruta de una experiencia fluida, sin distracciones.

---

## ⚡ Módulo nativo Rust (requerido)

Doremi acelera con **Rust** el procesamiento de imágenes, las variantes de color
del tema y las animaciones del fondo ambiental. Es parte obligatoria del proyecto:
hay que compilarlo antes de ejecutar la app.

```bash
# Con el venv activado (ver sección de desarrollo):
cd src/doremi/native_rs
maturin develop --release
```

---

## 🛠️ Desarrollo

```bash
# 1. Entorno (Python 3.13 recomendado; el repo fija 3.13.9 en .python-version)
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]" maturin

# 2. Compilar el módulo nativo Rust
cd src/doremi/native_rs && maturin develop --release && cd -

# 3. Ejecutar la app
doremi        # o: PYTHONPATH=src python -m doremi.main

# 4. Tests
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m pytest tests/ -q
```

---

## 🎨 Diseñado para la Elegancia

Doremi ha sido creado con una estética **Premium**, combinando colores vibrantes con una interfaz minimalista que hace que navegar por tu música sea un placer visual.

---

<p align="center">
  Creado con ❤️ para los amantes de la música en Linux por <b>Eirom</b>
</p>
