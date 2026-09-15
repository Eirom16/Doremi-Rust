from concurrent.futures import ThreadPoolExecutor

# Pool principal para tareas de red e imagen (descarga, escalado)
IO_POOL = ThreadPoolExecutor(max_workers=6, thread_name_prefix="doremi_io")

# Pool para tareas CPU (procesamiento de imágenes, extracción de colores)
CPU_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="doremi_cpu")
