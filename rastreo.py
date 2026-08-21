"""
Módulo: Rastreo y Trazabilidad
Crea envíos a partir de una ruta y registra el historial de estados
(pendiente, en ruta, entregado, incidencia) con marca de tiempo.
"""

from datetime import datetime
from typing import Dict, List

from modelos import Envio, EstadoEnvio, Ruta


class GestionRastreo:
    def __init__(self):
        self._envios: Dict[str, Envio] = {}
        self._contador = 0

    def crear_envio(self, ruta: Ruta) -> Envio:
        self._contador += 1
        envio = Envio(id=f"ENV-{self._contador:04d}", ruta=ruta)
        envio.historial.append((datetime.now(), EstadoEnvio.PENDIENTE, "Envío creado"))
        self._envios[envio.id] = envio
        return envio

    def actualizar_estado(self, envio_id: str, estado: EstadoEnvio, nota: str = "") -> Envio:
        envio = self._obtener(envio_id)
        envio.estado = estado
        envio.historial.append((datetime.now(), estado, nota))
        return envio

    def consultar_estado(self, envio_id: str) -> EstadoEnvio:
        return self._obtener(envio_id).estado

    def historial(self, envio_id: str) -> List:
        return self._obtener(envio_id).historial

    def _obtener(self, envio_id: str) -> Envio:
        if envio_id not in self._envios:
            raise KeyError(f"Envío no encontrado: {envio_id}")
        return self._envios[envio_id]
