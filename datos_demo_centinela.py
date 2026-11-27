"""Perfiles ficticios para la demostración de CENTINELA IA 2.13.

Este prototipo solo presenta UNA persona por base de datos.
No contiene datos personales verdaderos, dosis ni indicaciones reales.
Los teléfonos con ceros son ficticios: NO ENVIAR mensajes ni llamar.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from datetime import timedelta
import random

# Las horas solo sirven para probar la agenda de la persona ficticia.
RUTINAS_ANA_28 = [
    ("09:15", "Revisar el calendario"),
    ("11:30", "Cuidar las plantas"),
    ("15:30", "Mirar el álbum de fotos"),
    ("19:00", "Llamar a Lucía"),
]
MEDICAMENTOS_ANA_28 = [
    ("Medicamento C ", "Horario de demostración", "07:00,19:30", "Ejemplo para registrar dos horarios distintos"),
    ("Medicamento D ", "Horaio de demostración", "12:30", "Ejemplo de mediodía"),
    ("Medicamento E ", "Horario de demostración", "17:30", "Ejemplo de la tarde"),
]

SCENARIOS = {
    "ana": {
        "name": "Ana", "zone": "Coyoacán, Ciudad de México", "age_for_presentation": 74,
        "character": "Le gusta pintar, escuchar música y conversar con su familia.",
        "meds": [
            ("Medicamento A ", "Horario de demostración; no es una prescripción", "08:00,20:00", "Solo para probar confirmaciones por horario"),
            ("Medicamento B ", "Horario de demostración; no es una prescripción", "14:00", "No indica dosis reales"),
        ],
        "activities": [
            ("Escuchar música", "Diaria", "Preferencia: música tranquila"),
            ("Pintura y dibujo", "Semanal", "Preferencia: taller accesible"),
            ("Lectura", "Diaria", "Sesiones cortas con buena iluminación"),
            ("Paseo acompañado", "Fines de semana", "Solo si es adecuado y ha sido autorizado por profesional de salud"),
        ],
        "contacts": [("Lucía (ficticia)", "Hija", "0000000000"), ("Marta (ficticia)", "Cuidadora", "0000000001")],
        "confirmed": (0,"08:00"),
        "search": ("taller de pintura para adultos mayores", "Coyoacán, Ciudad de México"),
    },
    "jose": {
        "name": "José", "zone": "Tlalpan, Ciudad de México", "age_for_presentation": 81,
        "character": "Prefiere actividades tranquilas y requiere un ambiente accesible.",
        "meds": [
            ("Medicamento C (ficticio)", "Horario de demostración; no es una prescripción", "09:00,18:00", "Solo para demostración"),
            ("Medicamento D (ficticio)", "Horario de demostración; no es una prescripción", "12:00", "Sin dosis reales"),
        ],
        "activities": [
            ("Juegos de mesa", "Semanal", "Actividades sentado"),
            ("Música y recuerdos", "Diaria", "Conversar sobre canciones favoritas"),
            ("Movilidad suave sentado", "Diaria", "Únicamente ejercicios aprobados por profesional"),
            ("Taller de lectura", "Semanal", "Verificar rampas y accesibilidad"),
        ],
        "contacts": [("Raúl (ficticio)", "Hijo", "0000000000"), ("Teresa (ficticia)", "Cuidadora", "0000000001")],
        "confirmed": (0,"09:00"),
        "search": ("centro cultural accesible adultos mayores", "Tlalpan, Ciudad de México"),
    },
    "elena": {
        "name": "Elena", "zone": "Centro, Querétaro", "age_for_presentation": 69,
        "character": "Disfruta la jardinería, las manualidades y las actividades en comunidad.",
        "meds": [
            ("Medicamento E (ficticio)", "Horario de demostración; no es una prescripción", "07:30,19:30", "Solo para demostración"),
            ("Medicamento F (ficticio)", "Horario de demostración; no es una prescripción", "13:00", "Sin dosis reales"),
        ],
        "activities": [
            ("Jardinería ligera", "Semanal", "Evitar calor intenso y esfuerzos no autorizados"),
            ("Manualidades", "Semanal", "Actividades en mesa"),
            ("Escuchar audiolibros", "Diaria", "Preferencia: historias y literatura"),
            ("Reunión social", "Fines de semana", "Buscar actividades en centros comunitarios"),
        ],
        "contacts": [("Camila (ficticia)", "Hija", "0000000000"), ("Diego (ficticio)", "Hijo", "0000000001")],
        "confirmed": (0,"07:30"),
        "search": ("taller de manualidades adultos mayores", "Centro, Querétaro"),
    },
}


def cargar_escenario(escenario: str, db_path: str | Path, *, reiniciar: bool = False,
                    demo_28: bool = True):
    """Rellena solo una base de PRUEBA indicada explícitamente.

    Si ya existe y reiniciar=False, no borra nada. Si reiniciar=True,
    borra datos de esa base específica; usar una DB nueva para cada escenario.
    """
    if escenario not in SCENARIOS:
        raise ValueError("Escenario no encontrado. Usa: ana, jose o elena.")
    dest = Path(db_path).expanduser().resolve()
    if not dest.name.startswith("centinela_demo_") or dest.suffix != ".sqlite3":
        raise ValueError("Por seguridad la BD debe llamarse centinela_demo_*.sqlite3")
    if dest.exists() and not reiniciar:
        raise FileExistsError(f"Ya existe la BD {dest.name}; usa un archivo nuevo o reiniciar=True")
    os.environ["CENTINELA_DB"] = str(dest)
    import app
    # El archivo app puede estar importado previamente en Colab. Usamos la ruta explícita.
    app.DB_PATH = dest
    app.init_db()
    data = SCENARIOS[escenario]
    ana_28 = escenario == "ana" and demo_28
    rutinas = RUTINAS_ANA_28 if ana_28 else []
    medicamentos = data["meds"] + (MEDICAMENTOS_ANA_28 if ana_28 else [])
    actividades = data["activities"] + [
        (titulo, "Diaria", f"En la agenda a las {hora}") for hora, titulo in rutinas
    ]
    with app.database() as con:
        for table in ("seen","plan_period","extra_activities","goal_log","goals","checkins","preferences","voice_preferences"):
            con.execute(f"DELETE FROM {table}")
        con.execute("DELETE FROM confirmations")
        con.execute("DELETE FROM events")
        con.execute("DELETE FROM medicines")
        con.execute("DELETE FROM activities")
        con.execute("DELETE FROM contacts")
        con.execute("UPDATE person SET display_name=?,zone=? WHERE id=1", (data["name"],data["zone"]))
        first_id = None
        for i, med in enumerate(medicamentos):
            cur=con.execute("INSERT INTO medicines(person_id,name,instruction,times,notes) VALUES(1,?,?,?,?)",med)
            if i == data["confirmed"][0]:
                first_id=cur.lastrowid
        for activity in actividades:
            con.execute("INSERT INTO activities(person_id,name,frequency,notes) VALUES(1,?,?,?)",activity)
        for name,relationship,phone in data["contacts"]:
            con.execute("INSERT INTO contacts(person_id,name,relationship,phone) VALUES(1,?,?,?)",(name,relationship,phone))
        clock=app.now()
        day0=clock.date()
        today=day0.isoformat()
        declared=clock.isoformat(timespec="seconds")
        con.execute("INSERT INTO events(person_id,kind,event_key,detail,created_at) VALUES(1,?,?,?,?)",
                    ("demo","escenario_inicial",f"Se cargó el caso ficticio de {data['name']}. Los contactos y medicamentos no son reales.",declared))
        hh_demo = data["confirmed"][1]
        if hh_demo <= clock.strftime("%H:%M"):
            con.execute("INSERT INTO confirmations(medicine_id,on_date,at_time,declared_at,source) VALUES(?,?,?,?,?)",
                        (first_id,today,hh_demo,declared,"demo_ficticia"))
            con.execute("INSERT INTO events(person_id,kind,event_key,detail,created_at) VALUES(1,?,?,?,?)",
                        ("toma_declarada","confirmacion_demo",f"Confirmación ficticia del horario de las {hh_demo}",declared))
        # Semanas completas hasta ayer. Hoy queda disponible para interactuar.
        rnd=random.Random(47)
        days=84 if escenario=="ana" else 42
        first=day0-timedelta(days=days)
        medicines=con.execute("SELECT id,times FROM medicines").fetchall()
        for med in medicines:
            con.execute("INSERT INTO plan_period(med,hours,starts) VALUES(?,?,?)",
                        (med["id"],med["times"],str(first)+"T00:00"))
        gid=con.execute("INSERT INTO goals(title,weekdays,hh,tracked_from) VALUES(?,?,?,?)",
                        (data["activities"][0][0],f"{day0.weekday()},{(day0.weekday()+3)%7}","11:00",first.isoformat())).lastrowid
        goals=[(gid,{day0.weekday(),(day0.weekday()+3)%7})]
        if escenario=="ana":
            con.execute("INSERT INTO events(person_id,kind,event_key,detail,created_at) VALUES(1,'demo','ana_12_semanas','Evolución simulada de Ana durante 12 semanas',?)",(declared,))
            for title,weekdays,hh in [("Leer un cuento",{1,3,5},"16:30"),("Escuchar música",{0,2,4,6},"18:00")]:
                new_id=con.execute("INSERT INTO goals(title,weekdays,hh,tracked_from) VALUES(?,?,?,?)",
                          (title,",".join(map(str,sorted(weekdays))),hh,first.isoformat())).lastrowid
                goals.append((new_id,weekdays))
        if ana_28:
            for hora, titulo in rutinas:
                goal_id = con.execute(
                    "INSERT INTO goals(title,weekdays,hh,tracked_from) VALUES(?,?,?,?)",
                    (titulo, "0,1,2,3,4,5,6", hora, first.isoformat()),
                ).lastrowid
                goals.append((goal_id, set(range(7))))
            # Solo esta demo nueva trae permisos de muestra. Nunca se aplican al reabrirla.
            con.executemany("INSERT INTO preferences(name,enabled) VALUES(?,1)",
                            [(categoria,) for categoria in app.SHARE])
        for delta in range(days):
            day=first+timedelta(days=delta)
            progress=delta/(days-1)
            if escenario=="ana":
                if rnd.random()<0.79+0.18*progress:
                    def rating(start,gain):
                        return max(1,min(5,round(start+gain*progress+rnd.uniform(-0.75,0.75))))
                    note=rnd.choice(["Disfruté la música.","Hoy quise compañía.","Leí un rato."]) if delta%5==0 else ""
                    con.execute("INSERT INTO checkins VALUES(?,?,?,?)",(str(day),rating(2,2.6),rating(2.2,2.2),note))
            elif rnd.random()<0.72:
                con.execute("INSERT INTO checkins VALUES(?,?,?,?)",(str(day),rnd.choice([2,3,4,5]),rnd.choice([2,3,4]),""))
            for indice, (goal_id,weekdays) in enumerate(goals):
                if day.weekday() in weekdays:
                    if escenario=="ana":
                        outcome="Realizada" if rnd.random()<0.30+0.65*progress else rnd.choice(["Pospuesta","Cancelada"])
                    else:
                        outcome=rnd.choice(["Realizada","Realizada","Pospuesta","Cancelada"])
                    if not (ana_28 and (delta + 3 * indice) % 23 == 7):
                        con.execute("INSERT INTO goal_log VALUES(?,?,?,?)",(goal_id,str(day),outcome,"Preferí otro día" if outcome=="Pospuesta" else ""))
            if ana_28 and delta % 11 == 3:
                extra = ("Jugar dominó", "Dibujar en el patio")[(delta // 11) % 2]
                con.execute("INSERT INTO extra_activities(day,title,note) VALUES(?,?,?)", (str(day),extra,""))
            for med in medicines:
                for hh in med["times"].split(","):
                    stamp=f"{day}T{hh}:00"
                    shown=rnd.random()<0.9
                    if shown:
                        con.execute("INSERT INTO events(person_id,kind,event_key,detail,created_at) VALUES(1,'recordatorio',?,?,?)",
                                    (f"recordatorio:{med['id']}:{day}:{hh}","Aviso ficticio",stamp))
                        if rnd.random()<0.8:
                            con.execute("INSERT INTO seen VALUES(?,?,?,?)",(med["id"],str(day),hh,stamp))
                    chance=(0.48+0.45*progress if hh>="16:00" else 0.65+0.32*progress) if escenario=="ana" else (0.45 if hh>="16:00" else 0.88)
                    if rnd.random()<chance:
                        con.execute("INSERT INTO confirmations(medicine_id,on_date,at_time,declared_at,source) VALUES(?,?,?,?,?)",
                                    (med["id"],str(day),hh,stamp,"demo_ficticia"))
    return {"escenario":escenario,"nombre":data["name"],"base_de_datos":str(dest),
            "medicamentos":len(medicamentos),"horarios":sum(len(m[2].split(',')) for m in medicamentos),
            "rutinas_diarias_nuevas":len(rutinas),"actividades":len(actividades),
            "semanas_simuladas":days//7,"periodo":f"{first} a {day0-timedelta(days=1)}",
            "contactos_ficticios":len(data["contacts"])}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description="Cargar un escenario ficticio de CENTINELA IA 2.13")
    parser.add_argument("--escenario",choices=list(SCENARIOS),default="ana")
    parser.add_argument("--db",default=None)
    parser.add_argument("--reiniciar",action="store_true")
    args=parser.parse_args()
    chosen=args.db or f"centinela_demo_{args.escenario}.sqlite3"
    print(cargar_escenario(args.escenario,chosen,reiniciar=args.reiniciar))

