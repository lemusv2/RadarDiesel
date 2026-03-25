from functools import lru_cache
from flask import Flask, request, render_template_string
import urllib.parse

from DieselAlicante_v01 import (
    geocodificar_localidad,
    crear_url_komparing_por_coordenadas,
    obtener_gasolineras,
)


app = Flask(__name__)


HTML_TEMPLATE = """
<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Gasolineras">
    <title>Gasolineras baratas</title>
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <script>
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', function() {
                navigator.serviceWorker.register('/service-worker.js').catch(function(){});
            });
        }
    </script>
    <style>
        body { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 1.5rem; background: #f5f5f7; }
        h1 { font-size: 1.8rem; margin-bottom: 0.5rem; }
        form { background: #fff; padding: 1rem 1.25rem; border-radius: 0.75rem; box-shadow: 0 2px 6px rgba(0,0,0,0.08); margin-bottom: 1.5rem; }
        label { display: block; margin-top: 0.5rem; font-weight: 600; }
        input[type=text], select {
            width: 100%; padding: 0.5rem 0.75rem; margin-top: 0.25rem;
            border-radius: 0.5rem; border: 1px solid #d0d0d5; box-sizing: border-box;
        }
        button {
            margin-top: 0.75rem; padding: 0.5rem 1rem; border-radius: 999px;
            border: none; background: #007aff; color: white; font-weight: 600;
        }
        button:hover { background: #0063cc; cursor: pointer; }
        .section { background: #fff; padding: 1rem 1.25rem; border-radius: 0.75rem; box-shadow: 0 2px 6px rgba(0,0,0,0.08); margin-bottom: 1rem; }
        table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
        th, td { padding: 0.4rem 0.25rem; text-align: left; font-size: 0.9rem; }
        th { border-bottom: 1px solid #ddd; }
        a { color: #007aff; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .msg { margin-top: 0.5rem; color: #555; }
        .error { color: #b00020; font-weight: 600; }
        @media (min-width: 700px) {
            body { margin: 2rem auto; max-width: 800px; }
        }
    </style>
</head>
<body>
    <h1>Gasolineras más baratas</h1>
    <form method="get">
        <label>Localidad o código postal</label>
        <input type="text" name="localidad" placeholder="Ej. Valencia, 46001, Alicante" value="{{ localidad or '' }}">

        <label>Radio de búsqueda</label>
        <select name="radio_km">
            <option value="5" {% if radio_km == 5 %}selected{% endif %}>5 km</option>
            <option value="10" {% if radio_km == 10 %}selected{% endif %}>10 km</option>
        </select>

        <label>
            <input type="checkbox" name="incluye_gasolina95" value="1" {% if incluye_gasolina95 %}checked{% endif %}>
            Mostrar también Gasolina 95
        </label>

        <button type="submit">Buscar</button>
    </form>

    {% if error %}
        <p class="error">{{ error }}</p>
    {% endif %}

    {% if zona_label %}
        <p class="msg">Zona: <strong>{{ zona_label }}</strong> (radio: {{ radio_km }} km)</p>
    {% endif %}

    {% if resultados_diesel %}
    <div class="section">
        <h2>Top 5 Diésel (gasóleo A normal)</h2>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Gasolinera</th>
                    <th>Dirección</th>
                    <th>Precio €/L</th>
                    <th>Mapa</th>
                </tr>
            </thead>
            <tbody>
                {% for item in resultados_diesel %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ item.nombre }}</td>
                    <td>{{ item.direccion }}</td>
                    <td>{{ '%.3f'|format(item.precio) }}</td>
                    <td><a href="{{ item.url_maps }}" target="_blank">Ver</a></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if resultados_gas95 %}
    <div class="section">
        <h2>Top 5 Gasolina 95</h2>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Gasolinera</th>
                    <th>Dirección</th>
                    <th>Precio €/L</th>
                    <th>Mapa</th>
                </tr>
            </thead>
            <tbody>
                {% for item in resultados_gas95 %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ item.nombre }}</td>
                    <td>{{ item.direccion }}</td>
                    <td>{{ '%.3f'|format(item.precio) }}</td>
                    <td><a href="{{ item.url_maps }}" target="_blank">Ver</a></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}
</body>
</html>
"""


def calcular_top(gasolineras, indice_precio, n, zona_label):
    """Devuelve una lista de dicts con los top N más baratos."""
    filtradas = [g for g in gasolineras if g[indice_precio] and g[indice_precio] > 0]
    if not filtradas:
        return []
    ordenadas = sorted(filtradas, key=lambda g: g[indice_precio])[:n]

    resultados = []
    for nombre, direccion, precio_diesel, precio_gas95 in ordenadas:
        precio = precio_diesel if indice_precio == 2 else precio_gas95
        consulta = f"{nombre} {direccion} {zona_label}"
        url_maps = (
            "https://www.google.com/maps/search/"
            + urllib.parse.quote(consulta, safe="")
        )
        resultados.append(
            {
                "nombre": nombre,
                "direccion": direccion,
                "precio": precio,
                "url_maps": url_maps,
            }
        )
    return resultados


@app.route("/", methods=["GET"])
def index():
    localidad = request.args.get("localidad", "").strip()
    radio_km_str = request.args.get("radio_km", "5").strip()
    incluye_gasolina95 = request.args.get("incluye_gasolina95") == "1"

    try:
        radio_km = float(radio_km_str)
    except ValueError:
        radio_km = 5.0

    zona_label = None
    resultados_diesel = []
    resultados_gas95 = []
    error = None

    if localidad:
        try:
            lat, lon, display_name = geocodificar_localidad(localidad)
            if lat is None or lon is None:
                error = f"No se ha podido geocodificar '{localidad}'."
            else:
                zona_label = localidad
                if display_name:
                    zona_label = display_name

                url_xml = crear_url_komparing_por_coordenadas(
                    lat, lon, radio_km=radio_km
                )
                gasolineras = obtener_gasolineras(url_xml)
                if not gasolineras:
                    error = "No se han encontrado gasolineras en esa zona."
                else:
                    resultados_diesel = calcular_top(
                        gasolineras, indice_precio=2, n=5, zona_label=zona_label
                    )
                    if incluye_gasolina95:
                        resultados_gas95 = calcular_top(
                            gasolineras, indice_precio=3, n=5, zona_label=zona_label
                        )
        except Exception as exc:  # noqa: BLE001
            error = f"Error al obtener datos: {exc}"

    return render_template_string(
        HTML_TEMPLATE,
        localidad=localidad,
        radio_km=int(radio_km) if radio_km in (5, 10) else 5,
        incluye_gasolina95=incluye_gasolina95,
        zona_label=zona_label,
        resultados_diesel=resultados_diesel,
        resultados_gas95=resultados_gas95,
        error=error,
    )


if __name__ == "__main__":
    # 0.0.0.0 para que sea accesible desde el iPhone en la misma red WiFi
    app.run(host="0.0.0.0", port=5000, debug=True)
