"""
Modelos de datos para el sistema de Gestión de Distribución y Transporte.
Contiene las entidades base usadas por todos los módulos.

Las entidades incorporan atributos estándar de la literatura de gestión de
operaciones, inventarios y logística de distribución (lead time, demanda
promedio, stock de seguridad, clasificación ABC, ventanas de tiempo,
velocidad promedio para estimar tiempos de ruta, etc.) para que los
cálculos de los demás módulos (EOQ, punto de reorden, heurísticas de
ruteo, indicadores OTIF / fill rate) tengan soporte de datos real.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple


class EstadoPedido(str, Enum):
    CREADO = "CREADO"
    CONFIRMADO = "CONFIRMADO"
    BACKORDER = "BACKORDER"      # confirmado pero con faltante de stock
    ASIGNADO = "ASIGNADO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"


class EstadoEnvio(str, Enum):
    PENDIENTE = "PENDIENTE"
    EN_RUTA = "EN_RUTA"
    ENTREGADO = "ENTREGADO"
    INCIDENCIA = "INCIDENCIA"


class EstadoMantenimiento(str, Enum):
    PROGRAMADO = "PROGRAMADO"
    EN_PROCESO = "EN_PROCESO"
    COMPLETADO = "COMPLETADO"


class Prioridad(str, Enum):
    BAJA = "Baja"
    NORMAL = "Normal"
    ALTA = "Alta"
    URGENTE = "Urgente"


@dataclass
class Producto:
    codigo: str
    nombre: str
    categoria: str
    peso_kg: float                      # peso unitario
    volumen_m3: float                   # volumen unitario
    stock_minimo: int = 0
    stock_seguridad: int = 0            # inventario de seguridad ante variabilidad de demanda
    costo_unitario: float = 0.0         # costo de adquisición / producción
    precio_venta: float = 0.0
    lead_time_dias: int = 3             # tiempo de reposición del proveedor
    demanda_diaria_promedio: float = 0.0
    costo_pedido: float = 50000.0       # costo fijo de colocar una orden de compra (S de la fórmula EOQ)
    tasa_mantenimiento_anual: float = 0.25  # % del costo unitario que cuesta mantener 1 unidad en bodega un año
    clasificacion_abc: str = ""         # se calcula dinámicamente (A/B/C)
    unidad_medida: str = "unidad"


@dataclass
class ItemPedido:
    producto: Producto
    cantidad: int

    @property
    def peso_total(self) -> float:
        return self.producto.peso_kg * self.cantidad

    @property
    def volumen_total(self) -> float:
        return self.producto.volumen_m3 * self.cantidad

    @property
    def valor_total(self) -> float:
        return self.producto.precio_venta * self.cantidad


@dataclass
class Cliente:
    nombre: str
    direccion: str
    coordenadas: Tuple[float, float]     # (x, y) — km desde el centro de distribución
    zona: str = "Sin zona"
    tipo_cliente: str = "Minorista"      # Minorista | Mayorista | Institucional
    ventana_horaria: Tuple[str, str] = ("08:00", "18:00")


@dataclass
class Pedido:
    id: str
    cliente: Cliente
    items: List[ItemPedido] = field(default_factory=list)
    estado: EstadoPedido = EstadoPedido.CREADO
    prioridad: Prioridad = Prioridad.NORMAL
    fecha_creacion: datetime = field(default_factory=datetime.now)
    fecha_entrega_estimada: Optional[datetime] = None
    fecha_entrega_real: Optional[datetime] = None
    notas: str = ""

    @property
    def peso_total(self) -> float:
        return sum(i.peso_total for i in self.items)

    @property
    def volumen_total(self) -> float:
        return sum(i.volumen_total for i in self.items)

    @property
    def valor_total(self) -> float:
        return sum(i.valor_total for i in self.items)

    @property
    def tiempo_ciclo_dias(self) -> Optional[float]:
        """Días entre creación y entrega real (order cycle time)."""
        if self.fecha_entrega_real is None:
            return None
        return round((self.fecha_entrega_real - self.fecha_creacion).total_seconds() / 86400, 2)

    @property
    def entregado_a_tiempo(self) -> Optional[bool]:
        if self.fecha_entrega_real is None or self.fecha_entrega_estimada is None:
            return None
        return self.fecha_entrega_real <= self.fecha_entrega_estimada


@dataclass
class Vehiculo:
    placa: str
    tipo: str                          # ej: "furgón", "camión", "moto", "tractomula"
    capacidad_peso_kg: float
    capacidad_volumen_m3: float
    costo_km: float                    # costo variable por km (combustible + mantenimiento + peajes promedio)
    costo_fijo: float = 0.0            # costo fijo de despacho
    disponible: bool = True
    velocidad_promedio_kmh: float = 40.0
    tipo_combustible: str = "Diésel"
    rendimiento_km_por_galon: float = 10.0
    anio: int = 2020
    kilometraje_total: int = 0


@dataclass
class Ruta:
    id: str
    vehiculo: Vehiculo
    origen: Tuple[float, float]
    secuencia_pedidos: List[Pedido] = field(default_factory=list)
    distancia_km: float = 0.0
    costo_estimado: float = 0.0
    tiempo_estimado_horas: float = 0.0
    algoritmo: str = "Vecino más cercano + 2-opt"
    conductor: Optional["Conductor"] = None
    fecha_creacion: datetime = field(default_factory=datetime.now)

    @property
    def peso_total_kg(self) -> float:
        return sum(p.peso_total for p in self.secuencia_pedidos)

    @property
    def volumen_total_m3(self) -> float:
        return sum(p.volumen_total for p in self.secuencia_pedidos)

    @property
    def utilizacion_peso(self) -> float:
        if not self.vehiculo.capacidad_peso_kg:
            return 0.0
        return round((self.peso_total_kg / self.vehiculo.capacidad_peso_kg) * 100, 1)

    @property
    def utilizacion_volumen(self) -> float:
        if not self.vehiculo.capacidad_volumen_m3:
            return 0.0
        return round((self.volumen_total_m3 / self.vehiculo.capacidad_volumen_m3) * 100, 1)


@dataclass
class Envio:
    id: str
    ruta: Ruta
    estado: EstadoEnvio = EstadoEnvio.PENDIENTE
    historial: List[Tuple[datetime, EstadoEnvio, str]] = field(default_factory=list)
    eta: Optional[datetime] = None
    ubicacion_actual: Optional[Tuple[float, float]] = None
    porcentaje_avance: float = 0.0


@dataclass
class Conductor:
    id: str
    nombre: str
    licencia: str
    telefono: str = ""
    disponible: bool = True
    turno: str = "Diurno"              # Diurno | Nocturno
    calificacion: float = 5.0          # calificación promedio de desempeño (1-5)
    viajes_completados: int = 0


@dataclass
class Mantenimiento:
    id: str
    vehiculo: Vehiculo
    tipo: str  # ej: PREVENTIVO, CORRECTIVO
    inicio: datetime
    fin: datetime
    notas: str = ""
    estado: EstadoMantenimiento = EstadoMantenimiento.PROGRAMADO
    costo: float = 0.0
