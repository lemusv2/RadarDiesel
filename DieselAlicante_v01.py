"""
Programa para encontrar precios de Diésel y Gasolina 95 en función de una
localidad (o toda la zona de Alicante) usando el XML de Komparing.

Funcionalidad:
- Descarga el XML de Komparing con las gasolineras de la zona de Alicante.
- Lista las 5 gasolineras con el precio más barato de diésel (gasóleo A normal).
- Da la opción de abrir la gasolinera seleccionada en Google Maps.
- Pregunta si también se quieren ver los precios de Gasolina 95 y, en caso afirmativo,
  lista las 5 gasolineras más baratas y permite localizarlas también en Google Maps.
"""

import requests
import xml.etree.ElementTree as ET
import urllib.parse
import webbrowser
import math

# URL XML proporcionada por Komparing para la zona de Alicante y alrededores
URL_XML_POR_DEFECTO = (
    "https://www.komparing.com/es/gasolina/include/"
    "process-xml_maxLat-38.4584959860003_minLat-38.23218604266478_"
    "maxLong--0.2579177856445313_minLong--0.7047592163085938_"
    "zoomMapa-11_order-gsA_gsAe"
)


NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
RADIO_KM_POR_DEFECTO = 20.0
ZOOM_POR_DEFECTO = 11

@lru_cache(maxsize=100)
def geocodificar_localidad(localidad):
    ...
"""def geocodificar_localidad(localidad: str):
    
    Convierte una localidad (o CP/dirección) en (lat, lon) usando Nominatim (OSM).
    Devuelve (lat, lon, display_name) o (None, None, None) si no hay resultados.
    """
    q = localidad.strip()
    if not q:
        return None, None, None

    params = {
        "q": q,
        "format": "json",
        "limit": 1,
        "countrycodes": "es",
    }

    headers = {
        # Nominatim requiere un User-Agent identificable
        "User-Agent": "CursoCursor-DieselAlicante/1.0 (local script)",
    }

    resp = requests.get(NOMINATIM_SEARCH_URL, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json() or []
    if not data:
        return None, None, None

    item = data[0]
    try:
        lat = float(item["lat"])
        lon = float(item["lon"])
    except (KeyError, ValueError, TypeError):
        return None, None, None

    display_name = (item.get("display_name") or "").strip() or q
    return lat, lon, display_name


def crear_url_komparing_por_coordenadas(
    lat: float,
    lon: float,
    radio_km: float = RADIO_KM_POR_DEFECTO,
    zoom: int = ZOOM_POR_DEFECTO,
):
    """
    Genera una URL de Komparing (process-xml_...) centrada en (lat, lon),
    con una caja (bounding box) aproximada de `radio_km`.
    """
    # Aproximación suficiente para estas distancias (España)
    lat_delta = radio_km / 111.0
    cos_lat = abs(math.cos(math.radians(lat)))
    if cos_lat < 0.01:
        cos_lat = 0.01
    lon_delta = radio_km / (111.32 * cos_lat)

    min_lat = lat - lat_delta
    max_lat = lat + lat_delta
    min_lon = lon - lon_delta
    max_lon = lon + lon_delta

    base = "https://www.komparing.com/es/gasolina/include/"
    # Nota: si el valor es negativo, quedará "--0.123" (es correcto para este formato)
    return (
        base
        + "process-xml_"
        + f"maxLat-{max_lat:.6f}_minLat-{min_lat:.6f}_"
        + f"maxLong-{max_lon:.6f}_minLong-{min_lon:.6f}_"
        + f"zoomMapa-{int(zoom)}_order-gsA_gsAe"
    )


def obtener_gasolineras(url_xml: str):
    """
    Descarga el XML de Komparing y devuelve una lista de gasolineras.

    Cada elemento de la lista es una tupla:
    (nombre, direccion, precio_diesel, precio_gasolina95)
    """
    resp = requests.get(url_xml, timeout=15)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)

    gasolineras = []
    vistos = set()  # para evitar duplicados por (nombre, direccion)

    for marker in root.findall("marker"):
        nombre = marker.get("rotulo", "").strip()
        direccion = marker.get("direcc", "").strip()

        if not nombre or not direccion:
            continue

        # Precios en texto (pueden venir como "0.000" ó "1,459")
        diesel_txt = (marker.get("gasoleo_A_normal", "0") or "0").replace(",", ".")
        gas95_txt = (marker.get("gasolina_95", "0") or "0").replace(",", ".")

        try:
            precio_diesel = float(diesel_txt)
        except ValueError:
            precio_diesel = 0.0

        try:
            precio_gas95 = float(gas95_txt)
        except ValueError:
            precio_gas95 = 0.0

        clave = (nombre, direccion)
        if clave in vistos:
            continue
        vistos.add(clave)

        gasolineras.append((nombre, direccion, precio_diesel, precio_gas95))

    return gasolineras


def mostrar_top(gasolineras, indice_precio: int, n: int, etiqueta: str, localidad: str):
    """
    Ordena por el precio indicado (índice 2 -> diésel, índice 3 -> gasolina95),
    filtra precios > 0 y muestra las n gasolineras más baratas.

    Devuelve la lista de las n primeras gasolineras (ya ordenadas).
    """
    filtradas = [g for g in gasolineras if g[indice_precio] > 0]

    if not filtradas:
        print(f"No se han encontrado gasolineras con precio de {etiqueta}.")
        return []

    ordenadas = sorted(filtradas, key=lambda g: g[indice_precio])

    zona_txt = f"en '{localidad}'" if localidad.strip() else "en la zona"
    print(f"\nLas {n} gasolineras con el {etiqueta} más barato {zona_txt}:")
    for i, (nombre, direccion, precio_diesel, precio_gas95) in enumerate(
        ordenadas[:n], start=1
    ):
        precio = precio_diesel if indice_precio == 2 else precio_gas95
        print(f"{i}. {nombre} ({direccion}): {precio:.3f} €/L")

    return ordenadas[:n]


def abrir_en_maps(lista_gasolineras, mensaje: str, localidad: str):
    """
    Pregunta al usuario si quiere abrir alguna gasolinera en Google Maps.
    `lista_gasolineras` debe ser la lista ordenada (top N) devuelta por mostrar_top.
    """
    if not lista_gasolineras:
        return

    eleccion = input(mensaje).strip()

    if not eleccion:
        print("Saliendo sin abrir Google Maps.")
        return

    if not eleccion.isdigit():
        print("Entrada no válida. Debe ser un número.")
        return

    idx = int(eleccion)
    if not (1 <= idx <= len(lista_gasolineras)):
        print("Número fuera de rango.")
        return

    nombre, direccion, _, _ = lista_gasolineras[idx - 1]
    sufijo_localidad = localidad.strip() if localidad.strip() else "Alicante"
    consulta = f"{nombre} {direccion} {sufijo_localidad}"
    url_maps = "https://www.google.com/maps/search/" + urllib.parse.quote(consulta)
    print(f"Abriendo en el navegador: {url_maps}")
    webbrowser.open(url_maps)


def main():
    try:
        # Pedir una localidad/CP para centrar la búsqueda (si no, usamos Alicante por defecto)
        localidad_input = input(
            "Introduce una localidad o código postal (Enter para Alicante): "
        ).strip()

        zona_label = "Alicante"
        url = URL_XML_POR_DEFECTO

        if localidad_input:
            # Elegir radio de búsqueda
            while True:
                opcion_radio = input(
                    "Selecciona radio de búsqueda: [1] 10 km  [2] 20 km (Enter = 20 km): "
                ).strip()

                if opcion_radio == "1":
                    radio_km = 10.0
                    break
                elif opcion_radio == "2" or opcion_radio == "":
                    radio_km = 20.0
                    break
                else:
                    print("Opción no válida. Elige 1, 2 o pulsa Enter.")

            lat, lon, display_name = geocodificar_localidad(localidad_input)
            if lat is None or lon is None:
                print(
                    f"\nNo se ha podido geocodificar '{localidad_input}'. "
                    f"Se usará la zona por defecto (Alicante)."
                )
            else:
                url = crear_url_komparing_por_coordenadas(lat, lon, radio_km=radio_km)
                zona_label = localidad_input
                if display_name:
                    print(f"\nUbicación encontrada: {display_name}")

        gasolineras = obtener_gasolineras(url)
        if not gasolineras:
            print("No se han encontrado gasolineras en el XML.")
            return

        # Top 5 diésel
        top5_diesel = mostrar_top(
            gasolineras,
            indice_precio=2,
            n=5,
            etiqueta="diésel (gasóleo A normal)",
            localidad=zona_label,
        )
        abrir_en_maps(
            top5_diesel,
            "¿Quieres ver alguna de diésel en Google Maps? "
            "Escribe un número del 1 al 5 o pulsa Enter para salir: ",
            zona_label,
        )

        # Preguntar por Gasolina 95
        ver_gasolina = input(
            "\n¿Quieres ver también las 5 gasolineras más baratas de Gasolina 95? (s/n): "
        ).strip().lower()

        if ver_gasolina == "s":
            top5_gas95 = mostrar_top(
                gasolineras,
                indice_precio=3,
                n=5,
                etiqueta="Gasolina 95",
                localidad=zona_label,
            )
            abrir_en_maps(
                top5_gas95,
                "¿Quieres ver alguna de Gasolina 95 en Google Maps? "
                "Escribe un número del 1 al 5 o pulsa Enter para salir: ",
                zona_label,
            )
        else:
            print("No se mostrarán precios de Gasolina 95.")

    except requests.RequestException as e:
        print("Error al conectar o descargar el XML de Komparing:", e)
    except ET.ParseError as e:
        print("Error al analizar el XML recibido:", e)


if __name__ == "__main__":
    main()

# Programa para encontrar precios de Diesel en Alicante
# Listar las 5 gasolineras con el precio mas barato de diésel en Alicante
# Dar las opcion de localizar la gasolinera en Google Maps
# Preguntar si tambien quiero ver precios de Gasolina 95 
# Si es que si listar las 5 mas baratas y dar la opcion de localizarla en Google Maps
