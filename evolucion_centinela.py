"""Gráficas del cuidador construidas a partir de la agenda y las declaraciones del caso."""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from html import escape
from textwrap import fill

import numpy as np
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

TODAS = "todas"
SEMANA = "Últimos 7 días"
HOY = "Hoy"
ETIQUETA_TODAS = "Todas las actividades"
ESTADOS = ("Realizada", "Pospuesta", "Cancelada", "Sin registro", "Pendiente hoy")
ESTADOS_MED = ("Con confirmación", "Sin confirmación", "Más tarde")
COLORES = {
    "Realizada": ("#11665E", ""), "Pospuesta": ("#E8A652", "/"),
    "Cancelada": ("#86536F", "xx"), "Sin registro": ("#E8E9EA", ".."),
    "Pendiente hoy": ("#B8D5E7", "\\\\"),
    "Con confirmación": ("#11665E", ""), "Sin confirmación": ("#E8E9EA", ".."),
    "Más tarde": ("#B8D5E7", "\\\\"),
}
MAX_FILAS_GRAFICA = 12


@dataclass(frozen=True)
class Actividad:
    clave: str
    titulo: str
    dia: str
    hora: str
    estado: str
    programada: bool
    nota: str = ""


@dataclass
class Informe:
    encabezado: str
    graficas: dict = field(default_factory=dict)
    detalle: str = ""
    actividades: list = field(default_factory=list)
    actividad: str = TODAS
    semanas: list = field(default_factory=list)
    semana: str = ""


def fechas(inicio, fin):
    return (inicio + timedelta(days=i) for i in range((fin - inicio).days + 1))


def construir_agenda(metas, registros, inicio, fin, reloj):
    """Una aparición por rutina y fecha. Una edición del resultado ocupa la misma aparición."""
    por_meta = {(r["goal_id"], r["day"]): r for r in registros if r["goal_id"] is not None}
    agenda = []
    hoy = reloj.date().isoformat()
    hora_actual = reloj.strftime("%H:%M")
    for meta in metas:
        dias = set((meta["weekdays"] or "").split(","))
        hora = meta["hh"] or ""
        for fecha in fechas(inicio, fin):
            dia = fecha.isoformat()
            if dia < (meta["tracked_from"] or hoy) or str(fecha.weekday()) not in dias:
                continue
            registrado = por_meta.pop((meta["id"], dia), None)
            estado = "Pendiente hoy" if dia == hoy and (not hora or hora > hora_actual) else "Sin registro"
            if registrado and registrado["outcome"] in ESTADOS[:3]:
                estado = registrado["outcome"]
            agenda.append(Actividad(f"meta:{meta['id']}", meta["title"], dia, hora, estado, True,
                                    (registrado["note"] or "") if registrado else ""))
    # En bases anteriores podían anotarse metas fuera de los días de su agenda.
    for r in registros:
        gid = r["goal_id"]
        if gid is not None and (gid, r["day"]) not in por_meta:
            continue
        clave = f"fuera:{gid}" if gid is not None else "extra:" + r["title"].casefold()
        estado = r["outcome"] if r["outcome"] in ESTADOS[:3] else "Sin registro"
        agenda.append(Actividad(clave, r["title"], r["day"], "", estado, False, r["note"] or ""))
    return sorted(agenda, key=lambda a: (a.dia, not a.programada, not a.hora, a.hora, a.titulo.casefold(), a.clave))


def catalogo(agenda):
    """Conserva la identidad de rutinas distintas aunque compartan nombre u horario."""
    unicas = {}
    for a in agenda:
        unicas.setdefault(a.clave, a)
    orden = sorted(unicas.values(), key=lambda a: (not a.programada, not a.hora, a.hora, a.titulo.casefold(), a.clave))
    nombres = {a.clave: f"{a.hora or 'Sin hora'} · {a.titulo}" if a.programada else f"Extra · {a.titulo}"
               for a in orden}
    repeticiones = Counter(nombres.values())
    return {k: (f"{v} (rutina {k.split(':', 1)[1]})" if repeticiones[v] > 1 and not k.startswith("extra:") else v)
            for k, v in nombres.items()}


def bloques(inicio, fin, dias):
    tramos = []
    while inicio <= fin:
        cierre = min(inicio + timedelta(days=dias - 1), fin)
        tramos.append((inicio, cierre))
        inicio = cierre + timedelta(days=1)
    return tramos


def promedio(valores):
    valores = [v for v in valores if v is not None]
    return sum(valores) / len(valores) if valores else None


def decimal(valor):
    return "—" if valor is None else f"{valor:.2f}".replace(".", ",")


def fecha_corta(dia):
    return date.fromisoformat(dia).strftime("%d/%m/%Y")


def tabla(titulo, columnas, filas):
    filas = list(filas)
    if not filas:
        return ""
    def seguro(v):
        return escape(str(v), quote=True)
    th = "".join(f'<th scope="col">{seguro(t)}</th>' for t in columnas)
    cuerpo = "".join('<tr><th scope="row">' + seguro(f[0]) + '</th>' +
                     "".join('<td>' + seguro(v) + '</td>' for v in f[1:]) + '</tr>' for f in filas)
    return (f'<div class="weekly-table" tabindex="0" role="region" aria-label="{seguro(titulo)}">'
            f'<table><caption>{seguro(titulo)}</caption><thead><tr>{th}</tr></thead><tbody>{cuerpo}</tbody></table></div>')


def lienzo(alto):
    fig = Figure(figsize=(7.7, alto), dpi=116, layout="constrained", facecolor="#FFFFFF")
    ax = fig.subplots()
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(labelsize=10, length=0, pad=5)
    return fig, ax


def ejes_tiempo(ax, tramos, diario):
    x = range(len(tramos))
    ax.set_xticks(x, [i.strftime("%d/%m") for i, _ in tramos], rotation=25 if len(tramos) > 7 else 0)
    ax.set_xlim(-0.55, len(tramos)-0.45)
    ax.set_xlabel("Fecha (día/mes)" if diario else "Semana que comienza el (día/mes)", color="#364A52")


def grafica_bienestar(puntos, tramos, diario):
    if not any(p["energy"] is not None or p["sleep"] is not None for p in puntos):
        return None
    fig, ax = lienzo(3.05)
    for campo, etiqueta, color, marca, linea in [
        ("energy", "Energía", "#11665E", "o", "-"), ("sleep", "Descanso", "#8F482C", "s", "--")
    ]:
        valores = [p[campo] if p[campo] is not None else np.nan for p in puntos]
        ax.plot(range(len(tramos)), valores, label=etiqueta, color=color, marker=marca, linestyle=linea,
                linewidth=2, markersize=7 if campo == "energy" else 5, markerfacecolor="white" if campo == "sleep" else color)
    ax.set(ylim=(0.75, 5.25), yticks=range(1, 6), ylabel="Valor declarado (1–5)" if diario else "Media declarada (1–5)")
    ax.grid(axis="y", color="#DEE4E3")
    ejes_tiempo(ax, tramos, diario)
    ax.legend(loc="lower left", bbox_to_anchor=(0,1.01), borderaxespad=0, frameon=False, ncol=2)
    return fig


def grafica_estados(etiquetas, cuentas, estados, *, tramos=None, diario=False, unidad="Veces"):
    horizontal = tramos is None
    if not cuentas or not any(sum(c.values()) for c in cuentas):
        return None
    visibles = [e for e in estados if any(c[e] for c in cuentas)]
    maximo = max(sum(c.values()) for c in cuentas)
    nombres = [fill(e, width=28) for e in etiquetas] if horizontal else []
    alto = 1.9 + .42 * sum(1 + .5 * n.count("\n") for n in nombres) if horizontal else 3.55
    fig, ax = lienzo(max(2.9, alto))
    if horizontal:
        # Permite leer títulos largos sin confundir dos horarios con el mismo nombre.
        alto_fila = np.array([1 + .5 * n.count("\n") for n in nombres])
        pos = np.cumsum(alto_fila) - alto_fila / 2
    else:
        pos = np.arange(len(cuentas))
    base = np.zeros(len(cuentas))
    for estado in visibles:
        valores = np.array([c[estado] for c in cuentas])
        color, patron = COLORES[estado]
        kw = dict(color=color, hatch=patron, edgecolor="#454F53", linewidth=.55, label=estado)
        if horizontal:
            barras = ax.barh(pos, valores, left=base, height=.61, **kw)
        else:
            barras = ax.bar(pos, valores, bottom=base, width=.67, **kw)
        # Los números pequeños se conservan íntegros en la tabla situada bajo las gráficas.
        etiquetas_barra = [str(n) if n and n / maximo >= (.08 if horizontal else .15) else "" for n in valores]
        ax.bar_label(barras, labels=etiquetas_barra, label_type="center", fontsize=9,
                     bbox=dict(facecolor=color, edgecolor="none", pad=.5),
                     color="white" if estado in ("Realizada", "Con confirmación", "Cancelada") else "#182C35")
        base += valores
    if horizontal:
        ax.set_yticks(pos, nombres)
        for marca in ax.get_yticklabels():
            marca.set_parse_math(False)
        ax.invert_yaxis()
        for y, total in zip(pos, base):
            ax.annotate(str(int(total)), (total, y), xytext=(4, 0), textcoords="offset points",
                        va="center", color="#273E46", fontweight="semibold", fontsize=9)
        ax.set(xlabel=unidad + " · total al final de cada barra", xlim=(0, maximo*1.11))
        eje = ax.xaxis
    else:
        ejes_tiempo(ax, tramos, diario)
        ax.set(ylabel=unidad, ylim=(0, maximo*1.10))
        eje = ax.yaxis
    eje.set_major_locator(MaxNLocator(integer=True, nbins=6, min_n_ticks=1))
    eje.grid(color="#DCE3E4", linewidth=.75)
    ax.legend(loc="lower left", bbox_to_anchor=(0,1.02), ncol=min(3,len(visibles)), frameon=False,
              borderaxespad=0, columnspacing=1.1, handlelength=1.6, fontsize=9.5)
    return fig


def estado_medicamento(r, reloj):
    if r["confirmed"]:
        return "Con confirmación"
    if r["day"] == reloj.date().isoformat() and r["hh"] > reloj.strftime("%H:%M"):
        return "Más tarde"
    return "Sin confirmación"


def informe(nombre, reloj, inicio, fin, permisos, agenda, chequeos, horarios, actividad=TODAS, semana=""):
    persona = escape(nombre)
    partes = [f"<h3>Evolución de {persona}</h3>",
              f"<p>Del {inicio:%d/%m/%Y} al {fin:%d/%m/%Y} · {(fin-inicio).days+1} días.</p>"]
    res = Informe("")
    if not permisos:
        res.encabezado = "<p>La persona aún no comparte categorías de evolución.</p>"
        return res
    diario = (fin-inicio).days < 7
    tramos = bloques(inicio, fin, 1 if diario else 7)
    semanas = bloques(inicio, fin, 7)
    res.semanas = [(f"Del {i:%d/%m} al {f:%d/%m/%Y}", i.isoformat()) for i, f in semanas]
    vigentes = dict((i.isoformat(), (i,f)) for i,f in semanas)
    res.semana = semana if semana in vigentes else semanas[-1][0].isoformat()
    det_ini, det_fin = vigentes[res.semana]
    di, df = det_ini.isoformat(), det_fin.isoformat()
    detalle = []
    def abrir_detalle(titulo):
        abierto = " open" if not detalle else ""
        detalle.append(f'<details class="detalle-categoria"{abierto}><summary>{titulo}</summary>')
    # Esta segunda comprobación protege también a quien invoque la función sin la interfaz.
    nombres = catalogo(agenda) if "Metas" in permisos else {}
    res.actividades = [(ETIQUETA_TODAS, TODAS)] + [(v,k) for k,v in nombres.items()]
    res.actividad = actividad if actividad in nombres else TODAS
    filtrado = res.actividad != TODAS
    muestra = [a for a in agenda if not filtrado or a.clave == res.actividad] if "Metas" in permisos else []
    dias_realizados = {a.dia for a in muestra if a.estado == "Realizada"}
    seleccion = escape(nombres[res.actividad]) if filtrado else ""

    if "Metas" in permisos:
        abrir_detalle("Actividades")
        por_clave = defaultdict(Counter)
        for a in muestra:
            por_clave[a.clave][a.estado] += 1
        claves = [k for k in nombres if k in por_clave]
        de_agenda = [a for a in muestra if a.programada]
        hechas = sum(a.estado == "Realizada" for a in de_agenda)
        extras = sum(not a.programada and a.estado == "Realizada" for a in muestra)
        if muestra:
            cifras = []
            if de_agenda:
                cifras.append(f"{hechas} de {len(de_agenda)} apariciones en la agenda figuran como realizadas.")
                if filtrado:
                    cuentas = por_clave[res.actividad]
                    cifras.append(f"Pospuestas: {cuentas['Pospuesta']} · Canceladas: {cuentas['Cancelada']} · Sin registro: {cuentas['Sin registro']}.")
                    if cuentas["Pendiente hoy"]:
                        cifras.append(f"Pendientes hoy: {cuentas['Pendiente hoy']}.")
            if not filtrado or not de_agenda:
                cifras.append(f"Actividades extra realizadas: {extras}.")
            partes.append(f"<p><strong>{seleccion or 'Actividades del periodo'}</strong> · " + " ".join(cifras) + "</p>")
        por_tramo = [[a for a in muestra if i.isoformat() <= a.dia <= f.isoformat()] for i,f in tramos]
        if filtrado:
            cuentas = [Counter(a.estado for a in grupo) for grupo in por_tramo]
            # Un intervalo sin aparición de la rutina queda vacío, sin crear un resultado ficticio.
            graf = grafica_estados([], cuentas, ESTADOS, tramos=tramos, diario=diario, unidad="Registros y horarios")
        else:
            ver = claves[:MAX_FILAS_GRAFICA]
            graf = grafica_estados([nombres[k] for k in ver], [por_clave[k] for k in ver], ESTADOS,
                                   unidad="Apariciones de la actividad en el periodo")
            if len(claves) > len(ver):
                partes.append(f"<p>La gráfica muestra {len(ver)} de {len(claves)} actividades. Puedes elegir cualquiera en el filtro o consultar la tabla completa.</p>")
        res.graficas["Metas"] = graf
        if not graf:
            partes.append("<p>No hay actividades programadas ni registradas en este periodo.</p>")
        detalle.append(tabla("Resultados por actividad en el periodo", ["Actividad", "Programadas", *ESTADOS],
                      ([nombres[k], sum(por_clave[k].values()) if k.startswith("meta:") else "—",
                        *(por_clave[k][e] for e in ESTADOS)] for k in claves)))
        if muestra:
            filas_periodo = []
            for (i, f), grupo in zip(tramos, por_tramo):
                previstas = Counter(a.estado for a in grupo if a.programada)
                otras = Counter(a.estado for a in grupo if not a.programada)
                filas_periodo.append([i.strftime("%d/%m/%Y"), sum(previstas.values()), *(previstas[e] for e in ESTADOS),
                                      otras["Realizada"]])
            detalle.append(tabla("Actividades por día" if diario else "Actividades por semana",
                                 ["Fecha" if diario else "Inicio de semana", "Programadas", "Realizadas de la agenda",
                                  "Pospuestas", "Canceladas", "Sin registro", "Pendientes hoy", "Extras realizadas"],
                                 filas_periodo))
        detalle.append(tabla(f"Agenda y actividades extra · {det_ini:%d/%m} al {det_fin:%d/%m}",
                       ["Fecha", "Actividad", "Hora de agenda", "Tipo", "Estado", "Nota"],
                       ([fecha_corta(a.dia), a.titulo, a.hora or "—", "Agenda" if a.programada else "Extra",
                         a.estado, a.nota or "—"] for a in muestra if di <= a.dia <= df)))
        if not any(di <= a.dia <= df for a in muestra):
            detalle.append("<p>No hay apariciones de esta actividad en los días del detalle.</p>")
        detalle.append("</details>")

    if "Bienestar" in permisos:
        abrir_detalle("Bienestar")
        checks = {c["day"]: c for c in chequeos if not filtrado or c["day"] in dias_realizados}
        puntos = []
        for i, f in tramos:
            dias = [d.isoformat() for d in fechas(i,f) if not filtrado or d.isoformat() in dias_realizados]
            lecturas = [checks[d] for d in dias if d in checks]
            punto = {"dias":len(dias)}
            for k in ("energy","sleep"):
                valores = [c[k] for c in lecturas if c[k] is not None]
                punto[k] = promedio(valores)
                punto[k+"_n"] = len(valores)
            puntos.append(punto)
        res.graficas["Bienestar"] = grafica_bienestar(puntos, tramos, diario)
        if filtrado:
            partes.append(f"<p><strong>Bienestar</strong> · Solo se incluyen los días en que se marcó {seleccion} como realizada.</p>")
        if res.graficas["Bienestar"] is None:
            partes.append("<p>Faltan valores declarados de energía y descanso para esta selección.</p>")
        cab = ["Fecha" if diario else "Inicio de semana", "Energía / 5", "Días con energía",
               "Descanso / 5", "Días con descanso", "Días considerados"]
        detalle.append(tabla("Bienestar declarado · valores y días con respuesta", cab,
                       ([i.strftime("%d/%m/%Y"), decimal(p["energy"]), p["energy_n"], decimal(p["sleep"]),
                         p["sleep_n"], p["dias"]] for (i,_), p in zip(tramos,puntos))))
        filas = []
        for d in fechas(det_ini, det_fin):
            dia = d.isoformat()
            if filtrado and dia not in dias_realizados:
                continue
            c = checks.get(dia,{})
            filas.append([fecha_corta(dia), c.get("energy") if c.get("energy") is not None else "—",
                          c.get("sleep") if c.get("sleep") is not None else "—", c.get("note") or "—"])
        detalle.append(tabla("Bienestar día a día", ["Fecha","Energía / 5","Descanso / 5","Nota"], filas))
        detalle.append("</details>")

    if "Horarios" in permisos:
        abrir_detalle("Medicamentos")
        grupos = defaultdict(Counter)
        for r in horarios:
            grupos[(r["hh"],r["name"],r["med"])][estado_medicamento(r,reloj)] += 1
        claves_med = sorted(grupos)
        duplicados = Counter((hh, nombre) for hh, nombre, _ in claves_med)
        def etiqueta_med(k):
            hh, nombre_med, ident = k
            extra = f" (plan {ident})" if duplicados[(hh,nombre_med)] > 1 else ""
            return f"{hh} · {nombre_med}{extra}"
        ver = claves_med[:MAX_FILAS_GRAFICA]
        res.graficas["Horarios"] = grafica_estados([etiqueta_med(k) for k in ver], [grupos[k] for k in ver],
                                                  ESTADOS_MED, unidad="Horarios del plan en el periodo")
        if not grupos:
            partes.append("<p>No hay horarios de medicamentos previstos en este periodo.</p>")
        elif len(ver) < len(claves_med):
            partes.append(f"<p>La gráfica muestra {len(ver)} de {len(claves_med)} horarios. La tabla incluye todos.</p>")
        detalle.append(tabla("Confirmaciones declaradas por medicamento y horario", ["Horario y medicamento","Programados",*ESTADOS_MED],
                       ([etiqueta_med(k), sum(grupos[k].values()), *(grupos[k][e] for e in ESTADOS_MED)] for k in claves_med)))
        if horarios:
            filas_horarios = []
            for i, f in tramos:
                filas = [r for r in horarios if i.isoformat() <= r["day"] <= f.isoformat()]
                cuentas = Counter(estado_medicamento(r,reloj) for r in filas)
                sin_aviso = sum(not (r["confirmed"] or r["seen"] or r["generated"]) and estado_medicamento(r,reloj) != "Más tarde" for r in filas)
                filas_horarios.append([i.strftime("%d/%m/%Y"),len(filas),*(cuentas[e] for e in ESTADOS_MED),sin_aviso])
            detalle.append(tabla("Horarios por día" if diario else "Horarios por semana",
                                ["Fecha" if diario else "Inicio de semana","Programados",*ESTADOS_MED,"Sin aviso ni declaración registrados"],
                                filas_horarios))
        detalle.append(tabla(f"Registro de medicamentos · {det_ini:%d/%m} al {det_fin:%d/%m}",
                       ["Fecha","Hora del plan","Medicamento","Estado","Hora de confirmación","Aviso generado","Aviso visto"],
                       ([fecha_corta(r["day"]),r["hh"],r["name"],estado_medicamento(r,reloj),
                         r["confirmed"][11:16] if r["confirmed"] else "—","Sí" if r["generated"] else "Sin registro",
                         r["seen"][11:16] if r["seen"] else "—"] for r in horarios if di <= r["day"] <= df)))
        detalle.append("</details>")
    res.encabezado = "".join(partes)
    if any(fig is not None for fig in res.graficas.values()):
        res.encabezado += '<p class="pista-deslizar">Desliza la gráfica hacia los lados para verla completa. También puedes abrir las cifras por fecha.</p>'
    res.detalle = "".join(detalle)
    return res

