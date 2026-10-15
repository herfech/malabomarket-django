import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image

MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB por foto, antes de procesar
MAX_DIMENSION = 1600  # px, lado más largo
JPEG_QUALITY = 82


def process_uploaded_image(uploaded_file):
    """
    Toma un archivo subido por el usuario y devuelve un ContentFile JPEG
    seguro para guardar: revalidado como imagen real (no solo por su
    extensión), redimensionado y sin metadatos EXIF (lo que además
    elimina cualquier coordenada GPS que la foto pudiera traer).

    Lanza ValidationError con un mensaje en español si el archivo no es
    una imagen válida o excede el tamaño permitido.
    """
    if uploaded_file.size > MAX_UPLOAD_BYTES:
        raise ValidationError(f"La imagen {uploaded_file.name} pesa más de 8 MB.")

    try:
        image = Image.open(uploaded_file)
        image.verify()  # detecta archivos corruptos o que no son imágenes de verdad
    except Exception as exc:
        raise ValidationError(f"El archivo {uploaded_file.name} no es una imagen válida.") from exc

    # .verify() deja el objeto inutilizable para seguir operando — se reabre.
    uploaded_file.seek(0)
    image = Image.open(uploaded_file)
    image = image.convert("RGB")  # normaliza PNG/WEBP/etc. y descarta canal alfa
    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))

    buffer = ContentFile(b"")
    # Guardar sin pasar exif=... es lo que efectivamente elimina los
    # metadatos originales (orientación, modelo de cámara, GPS, etc.).
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)

    filename = f"{uuid.uuid4().hex}.jpg"
    return ContentFile(buffer.read(), name=filename)
