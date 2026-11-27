"""CENTINELA IA  DEMO.

Cada pestaña elige el perfil de la persona o el del cuidador desde la portada.
NO es un dispositivo médico, detector de caídas ni un sistema de emergencias.
Usar únicamente datos ficticios para pruebas, especialmente con enlaces compartidos.
"""
from __future__ import annotations

import base64
import html
import io
import logging
import os
import re
import sqlite3
import sys
import tempfile
import threading
import time
import unicodedata
from datetime import datetime, date, timedelta
from itertools import groupby
from pathlib import Path
from urllib.parse import quote, quote_plus
from zoneinfo import ZoneInfo

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
import gradio as gr
import numpy as np
import pandas as pd
import requests

import evolucion_centinela as evolucion
import avisos_centinela as avisos
import voces_centinela as voces

APP_TZ = ZoneInfo(os.environ.get("APP_TIMEZONE", "America/Mexico_City"))
# La portada es de acceso libre. El cuaderno selecciona explícitamente la base del ensayo.
DB_PATH = Path(os.environ.get("CENTINELA_DB") or "centinela_demo_coloquio_ana.sqlite3")
PERSON_ID = 1  # Prototipo de UNA persona. Multiusuario requiere aislamiento adicional.
TIME_PATTERN = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d\Z")
MED_HEADERS = ["ID", "Medicamento", "Indicación del profesional", "Horarios", "Notas"]
ACT_HEADERS = ["ID", "Actividad favorita", "Frecuencia", "Accesibilidad y notas"]
CONTACT_HEADERS = ["ID", "Nombre", "Relación", "Teléfono"]

CSS = """
/* CENTINELA IA 2.13 — tema de sistema. Gradio aplica .dark según el dispositivo. */
:root {
    --cent-bg: #f7f7f2;
    --cent-surface: #ffffff;
    --cent-ink: #17324d;
    --cent-body: #334b55;
    --cent-muted: #526775;
    --cent-line: #dfe6e0;
    --cent-green: #245a51;
    --cent-green-hover: #19443c;
    --cent-accent: #d9aa73;
    --cent-mark-bg: #dcece6;
    --cent-hero: #e9f1ed;
    --cent-hero-line: #d5e8de;
    --cent-hero-ink: #183d37;
    --cent-tag: #e8f2ed;
    --cent-tag-ink: #204e45;
    --cent-warning: #fff0d4;
    --cent-warning-ink: #744500;
    --cent-success: #e5f2e5;
    --cent-success-ink: #215b30;
    --cent-help: #fff4f1;
    --cent-help-line: #ecd4ca;
    --cent-help-ink: #73322a;
    --cent-disclaimer: #fffdf7;
    --cent-disclaimer-line: #eee0be;
    --cent-disclaimer-ink: #664d26;
    --cent-camera-note: #fff5e7;
    --cent-camera-line: #ab6a32;
    --cent-camera-ink: #633d1a;
    --cent-camera-on: #e9f7ef;
    --cent-camera-on-line: #27755a;
    --cent-camera-on-ink: #1d4f3b;
    --cent-shadow: rgba(33,61,54,.055);
}
/* La clase .dark es añadida por Gradio cuando el navegador/sistema prefiere el modo oscuro.
   Este selector también sirve al forzar el tema mediante ?__theme=dark en las pruebas. */
:root.dark, .dark {
    --cent-bg: #101b24;
    --cent-surface: #1c2b35;
    --cent-ink: #f0f5f5;
    --cent-body: #d8e3e7;
    --cent-muted: #b8cbd1;
    --cent-line: #425564;
    --cent-green: #337d70;
    --cent-green-hover: #3c9484;
    --cent-accent: #ffcf92;
    --cent-mark-bg: #25463f;
    --cent-hero: #1c3937;
    --cent-hero-line: #3a6258;
    --cent-hero-ink: #f0f8f5;
    --cent-tag: #254d45;
    --cent-tag-ink: #e0faf2;
    --cent-warning: #55401e;
    --cent-warning-ink: #ffdeb3;
    --cent-success: #1d4936;
    --cent-success-ink: #c1f3d4;
    --cent-help: #452c2b;
    --cent-help-line: #95635b;
    --cent-help-ink: #ffe5df;
    --cent-disclaimer: #39351f;
    --cent-disclaimer-line: #82764e;
    --cent-disclaimer-ink: #fff0c9;
    --cent-camera-note: #3f3221;
    --cent-camera-line: #ac8751;
    --cent-camera-ink: #ffe6c2;
    --cent-camera-on: #1d4438;
    --cent-camera-on-line: #66b18b;
    --cent-camera-on-ink: #d3f7e2;
    --cent-shadow: rgba(0,0,0,.20);
}
.gradio-container {box-sizing:border-box; width:100% !important; min-width:0 !important;
    max-width:min(100%,1150px) !important; margin-inline:auto !important; font-size:18px !important;}
.gradio-container, body {background:var(--cent-bg) !important; color:var(--cent-ink) !important;}
.gradio-container label, .gradio-container input, .gradio-container textarea {font-size:1rem !important;}
.gradio-container button {min-height:54px !important; border-radius:14px !important; font-size:1rem !important; font-weight:650 !important;}
.gradio-container button.primary {background:var(--cent-green) !important; color:white !important; border-color:var(--cent-green) !important;}
.gradio-container button.primary:hover {background:var(--cent-green-hover) !important;}
.gradio-container [role="tab"] {min-height:53px; font-size:1rem !important;}
.gradio-container :focus-visible {outline:3px solid var(--cent-accent) !important; outline-offset:3px;}
.cent-brand {display:flex;align-items:center;gap:14px;padding:12px 0 14px;}
.cent-mark {display:grid;place-items:center;background:var(--cent-mark-bg);border-radius:18px;min-width:62px;height:62px;font-size:32px;}
.cent-brand h1 {font-size:2rem;line-height:1.15;margin:0;color:var(--cent-ink);}
.cent-brand p {font-size:1rem;color:var(--cent-muted);margin:2px 0;}
.cent-hero {border-radius:20px;background:var(--cent-hero);padding:24px;border:1px solid var(--cent-hero-line);margin:4px 0 14px;}
.cent-hero h2 {font-size:1.8rem;line-height:1.2;color:var(--cent-hero-ink);margin:0 0 10px;}
.cent-hero p {font-size:1.05rem;margin:0;line-height:1.5;color:var(--cent-body);}
.cent-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:12px 0;}
.cent-card {background:var(--cent-surface);padding:22px;border:1px solid var(--cent-line);border-radius:18px;box-shadow:0 2px 5px var(--cent-shadow);color:var(--cent-body);}
.cent-card h3 {font-size:1.16rem;color:var(--cent-ink);margin:0 0 10px;}
.cent-card p {font-size:1rem;margin:8px 0;color:var(--cent-body);line-height:1.5;}
.cent-card strong {color:var(--cent-ink);}
.cent-card .cent-big {font-size:1.6rem;font-weight:750;color:var(--cent-ink);}
.cent-tag {font-size:.93rem;border-radius:999px;padding:5px 12px;background:var(--cent-tag);color:var(--cent-tag-ink);display:inline-block;font-weight:650;}
.cent-tag.warning {background:var(--cent-warning);color:var(--cent-warning-ink);}
.cent-tag.done {background:var(--cent-success);color:var(--cent-success-ink);}
.cent-muted {font-size:.94rem;color:var(--cent-muted);line-height:1.5;}
.cent-dose {display:flex;justify-content:space-between;align-items:center;gap:15px;padding:13px 0;border-bottom:1px solid var(--cent-line);}
.cent-dose:last-child {border-bottom:0;}
.cent-help {padding:12px 18px;background:var(--cent-help);border-radius:14px;border:1px solid var(--cent-help-line);color:var(--cent-help-ink);}
.cent-disclaimer {background:var(--cent-disclaimer);border:1px solid var(--cent-disclaimer-line);padding:14px 17px;border-radius:14px;color:var(--cent-disclaimer-ink);font-size:.92rem;line-height:1.5;}
.cent-section {padding-top:8px;font-size:1.35rem;color:var(--cent-ink);font-weight:750;}
.cent-video-shell {border-radius:18px;border:1px solid var(--cent-line);overflow:hidden;background:#142632;min-height:230px;display:grid;place-items:center;color:#eaf2f3;}
.cent-video-shell img {width:100%;height:auto;max-height:470px;display:block;object-fit:contain;background:#142632;}
.cent-video-placeholder {text-align:center;padding:54px 24px;line-height:1.6;font-size:1.08rem;}
.cent-video-placeholder strong {font-size:1.35rem;display:block;margin:8px 0;color:white;}
.cent-camera-note {padding:16px;border:2px solid var(--cent-camera-line);background:var(--cent-camera-note);color:var(--cent-camera-ink);border-radius:14px;line-height:1.5;}
.cent-camera-on {border:2px solid var(--cent-camera-on-line);background:var(--cent-camera-on);padding:12px;border-radius:14px;color:var(--cent-camera-on-ink);font-weight:700;}
.cent-session-bar {margin-bottom:8px;align-items:center;}
.cent-session-caption {font-weight:650;color:var(--cent-muted);margin:0;}
.gradio-container button.cent-logout {min-height:48px !important;}
@media(max-width:690px){.cent-grid{grid-template-columns:1fr}.cent-hero{padding:18px}.cent-brand h1{font-size:1.7rem}.cent-dose{align-items:start;flex-direction:column}.gradio-container{font-size:17px !important;}}

:root {--cent-bg:#faf6ee;--cent-green:#6b3543;--cent-green-hover:#542634;--cent-accent:#8c3547;}
.dark {--cent-bg:#171b25;--cent-green:#71394b;--cent-green-hover:#814356;--cent-accent:#ffc489;}
#adult-space {font-family:system-ui,sans-serif;}
#adult-space button,#adult-space label,#adult-space input,#adult-space textarea {font-size:1.125rem !important;}
#adult-space .cent-card {margin:.6rem 0;}
#adult-space .cent-card p,#adult-space .day-now p {font-size:1.16rem;line-height:1.55;}
#adult-space .day-next {font-weight:700;}
.day-now {display:flex;align-items:center;gap:1.25rem;padding:1.4rem;border-radius:1.2rem;}
.day-now.morning {background:#fff0cd;color:#392b15;}
.day-now.afternoon {background:#ffdfce;color:#48281d;}
.day-now.night {background:#302f4d;color:#fff5e4;}
.dark .day-now.morning {background:#453a27;color:#fff0cd;}
.dark .day-now.afternoon {background:#4c342f;color:#ffdfce;}
.dark .day-now.night {background:#34344e;color:#fff5e4;}
.day-now h2,.day-now p,.day-now strong {color:inherit !important;margin:.2rem 0;}
.day-now h2 {font-size:clamp(1.6rem,4vw,2.3rem);line-height:1.18;}
.day-now strong {font-size:1.45rem;}
.day-icon {font-size:clamp(2.4rem,7vw,4.5rem);line-height:1;}
.day-section {font-size:1.25rem;margin:1.2rem 0 .35rem;color:var(--cent-ink);}
@media(max-width:600px){.day-now{padding:1rem;gap:.8rem;}#adult-space .cent-card{padding:1rem;}}

#easy-tools {position:sticky;top:0;z-index:12;background:var(--cent-bg);padding:.25rem;}
#easy-tools button {min-width:0!important;flex:1 1 0!important;}
#adult-space.large-type :is(p,label,input,textarea,button,span,h3,legend) {font-size:1.45rem!important;line-height:1.45!important;}
#adult-space.large-type h2 {font-size:2rem!important;}
#single-mic {min-height:68px!important;}
@media(max-width:620px){#easy-tools {display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr));}#easy-tools button {white-space:normal;overflow-wrap:anywhere;padding:.3rem!important;}}

.weekly-table {overflow-x:auto; width:100%; max-width:100%; min-width:0; contain:inline-size; margin:1rem 0;}
.weekly-table table {width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums;}
.weekly-table caption {text-align:left; padding:.35rem 0; font-weight:600;}
.weekly-table th,.weekly-table td {padding:.45rem .6rem; border-bottom:1px solid var(--cent-line); text-align:left;}
#detalle-evolucion .detalle-categoria {border-top:1px solid var(--cent-line);padding:.4rem 0;}
#detalle-evolucion summary {font-weight:700;cursor:pointer;color:var(--cent-ink);padding:.5rem .2rem;}
#detalle-evolucion caption {color:var(--cent-ink);font-size:1.05rem;margin:.35rem 0;}
#detalle-evolucion thead {background:var(--cent-mark-bg);color:var(--cent-ink);}
#detalle-evolucion td,#detalle-evolucion th {vertical-align:top;}
#resumen-evolucion h3 {font-size:1.4rem;margin:.25rem 0;}
#resumen-evolucion p {margin:.3rem 0;color:var(--cent-body);}
#resumen-evolucion .pista-deslizar {display:none;}
@media(max-width:640px){
    #resumen-evolucion .pista-deslizar {display:block;font-size:.95rem;}
    .weekly-chart .matplotlib {display:block!important;overflow-x:auto;overscroll-behavior-x:contain;}
    .weekly-chart .matplotlib img {display:block;width:690px!important;min-width:690px;max-width:none!important;height:auto!important;}
}
.weekly-chart > label.float {position:static !important; display:flex; width:fit-content; max-width:100%;
    margin:.55rem .75rem .2rem; background:transparent !important; color:var(--cent-ink) !important;
    box-shadow:none; font-weight:700;}
.cent-review {border-inline-start:5px solid var(--cent-accent); padding:.8rem 1rem; background:var(--cent-surface);}
.cent-review p {margin:.3rem 0 0; line-height:1.5;}
#perfil-portada {margin:clamp(.8rem,3vw,2.4rem) auto; width:100%; max-width:56rem;}
#perfil-portada h2 {font-size:clamp(1.7rem,4vw,2.45rem);line-height:1.16;margin:0 0 .45rem;color:var(--cent-ink);}
#perfil-portada p {color:var(--cent-body);line-height:1.5;}
#perfil-portada .perfil-opcion {box-sizing:border-box;border:1px solid var(--cent-line);border-radius:18px;
    background:var(--cent-surface);padding:clamp(1rem,3vw,1.5rem);justify-content:space-between;}
#perfil-portada h3 {margin:0 0 .35rem;font-size:1.28rem;color:var(--cent-ink);}
#perfil-portada .perfil-opcion button {min-height:58px !important;}
@media(max-width:640px){#perfil-portada .perfil-fila {flex-direction:column;}}
.aviso-principal,.aviso-contexto {color:var(--cent-body);background:var(--cent-surface);border:1px solid var(--cent-line);border-radius:14px;}
.aviso-principal {padding:clamp(.8rem,2vw,1.2rem);margin:.2rem 0 .3rem;}
.aviso-principal p,.aviso-contexto p {margin:.2rem 0;line-height:1.5;}
.aviso-principal strong,.aviso-contexto strong,.aviso-principal h2,.aviso-principal h3 {color:var(--cent-ink);}
.aviso-acciones {display:flex;flex-wrap:wrap;gap:.5rem;margin:.6rem 0 0;}
.aviso-acciones button {background:var(--cent-surface);color:var(--cent-ink);border:1px solid var(--cent-muted);
    padding:.45rem .9rem;border-radius:10px;font-weight:600;min-height:44px;cursor:pointer;}
.aviso-acciones button:focus-visible,.aviso-principal a:focus-visible {outline:3px solid var(--cent-accent);outline-offset:2px;}
.aviso-principal [hidden] {display:none !important;}
#aviso-reproductor audio {width:min(100%,30rem);margin-top:.7rem;}
#aviso-integral {max-width:76ch;margin:1rem 0 .2rem;overflow-wrap:anywhere;}
#aviso-integral h2 {margin:.6rem 0;font-size:1.4rem;}
#aviso-integral h3 {margin:.8rem 0 .2rem;font-size:1.1rem;}
#aviso-integral dt {font-weight:650;} #aviso-integral dd {margin:0 0 .4rem;}
#aviso-integral a {color:var(--cent-ink);text-decoration:underline;}
.aviso-contexto {padding:.65rem 1rem;border-inline-start:4px solid var(--cent-accent);margin:.25rem 0;}
#perfil-portada {margin:clamp(.35rem,1.2vw,1rem) auto;}
@media(max-width:640px){
    .aviso-principal{padding:.65rem .8rem;font-size:1rem;}
    .aviso-acciones{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);}
    .aviso-acciones button{padding:.25rem .4rem;line-height:1.25;}
    #perfil-portada .perfil-opcion{padding:0;border:0;background:transparent;min-width:0!important;}
    #perfil-portada .descripcion-perfil{display:none;}
    #perfil-portada .perfil-fila{gap:.55rem;}
    #perfil-portada .perfil-opcion button{width:100%;}
}

"""


def safe(value, length=240):
    return html.escape(str(value or "").strip()[:length], quote=True)


def clean(value, length=240):
    return str(value or "").strip()[:length]


def norm(value):
    return "".join(x for x in unicodedata.normalize("NFD", str(value).lower()) if unicodedata.category(x) != "Mn")


def now():
    return datetime.now(APP_TZ)


def database():
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA busy_timeout=15000")
    return c


def sql_rows(sql, params=()):
    with database() as c:
        return [dict(x) for x in c.execute(sql, params).fetchall()]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with database() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS person (
            id INTEGER PRIMARY KEY, display_name TEXT NOT NULL, zone TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS voice_preferences (
            person_id INTEGER PRIMARY KEY REFERENCES person(id) ON DELETE CASCADE,
            voice_id TEXT NOT NULL, pace TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL REFERENCES person(id),
            name TEXT NOT NULL, instruction TEXT NOT NULL, times TEXT NOT NULL,
            notes TEXT DEFAULT '', active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS confirmations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id INTEGER NOT NULL REFERENCES medicines(id),
            on_date TEXT NOT NULL, at_time TEXT NOT NULL,
            declared_at TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual',
            UNIQUE (medicine_id, on_date, at_time)
        );
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL REFERENCES person(id),
            name TEXT NOT NULL, frequency TEXT NOT NULL, notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL REFERENCES person(id),
            name TEXT NOT NULL, relationship TEXT NOT NULL, phone TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL REFERENCES person(id),
            kind TEXT NOT NULL, event_key TEXT UNIQUE,
            detail TEXT NOT NULL, created_at TEXT NOT NULL
        );
        INSERT OR IGNORE INTO person(id,display_name,zone) VALUES(1,'Ana','');
        """)
        init_evolution(c)


DAYS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
OUTCOMES = ["Realizada","Pospuesta","Cancelada"]
SHARE = ["Bienestar","Metas","Horarios"]
PERIOD_DEMO = "12 semanas de demostración"
PERIOD_RECENT = "Últimas 12 semanas"


def init_evolution(c):
    # Una persona por base, como en los perfiles originales. Registrar la vigencia
    # desde esta migración evita inventar horarios anteriores al seguimiento.
    c.executescript("""
        CREATE TABLE IF NOT EXISTS checkins(day TEXT PRIMARY KEY, energy INTEGER, sleep INTEGER, note TEXT);
        CREATE TABLE IF NOT EXISTS goals(id INTEGER PRIMARY KEY, title TEXT, weekdays TEXT, hh TEXT, tracked_from TEXT);
        CREATE TABLE IF NOT EXISTS goal_log(goal INTEGER REFERENCES goals(id), day TEXT, outcome TEXT, note TEXT,
            PRIMARY KEY(goal,day));
        CREATE TABLE IF NOT EXISTS extra_activities(day TEXT NOT NULL, title TEXT NOT NULL COLLATE NOCASE,
            note TEXT DEFAULT '', PRIMARY KEY(day,title));
        CREATE TABLE IF NOT EXISTS preferences(name TEXT PRIMARY KEY, enabled INTEGER);
        CREATE TABLE IF NOT EXISTS plan_period(med INTEGER PRIMARY KEY REFERENCES medicines(id),
            hours TEXT, starts TEXT, ends TEXT);
        CREATE TABLE IF NOT EXISTS seen(med INTEGER REFERENCES medicines(id),day TEXT,hh TEXT,stamp TEXT,
            PRIMARY KEY(med,day,hh));
    """)
    c.execute("""INSERT OR IGNORE INTO plan_period(med,hours,starts)
                 SELECT id,times,? FROM medicines WHERE active=1""",(now().isoformat(timespec="minutes"),))
    # La transacción de escritura ya está abierta. Dos arranques no pueden migrar a la vez.
    if "tracked_from" not in {r[1] for r in c.execute("PRAGMA table_info(goals)")}:
        c.execute("ALTER TABLE goals ADD COLUMN tracked_from TEXT")
    c.execute("""UPDATE goals SET tracked_from=COALESCE(
                (SELECT MIN(l.day) FROM goal_log l WHERE l.goal=goals.id), ?)
                WHERE tracked_from IS NULL""", (now().date().isoformat(),))


def scheduled_goals(day):
    rows = sql_rows("""SELECT g.*, l.outcome FROM goals g LEFT JOIN goal_log l
                       ON l.goal=g.id AND l.day=? WHERE (g.tracked_from IS NULL OR g.tracked_from<=?) ORDER BY (COALESCE(g.hh,'')=''),g.hh,g.title,g.id""",
                    (day.isoformat(),day.isoformat()))
    return [g for g in rows if str(day.weekday()) in g["weekdays"].split(",")]


def today_agenda():
    return [f"{g['hh'] or 'Sin hora fija'} · {g['title']}" for g in scheduled_goals(now().date())]


def save_checkin(energy,sleep,note,request:gr.Request):
    guard(request,{"adult"})
    values=[int(v) if str(v) in ("1","2","3","4","5") else None for v in (energy,sleep)]
    note=clean(note,350)
    if not any(values) and not note:
        return "Puedes omitir el chequeo. No se guardó ninguna respuesta."
    with database() as c:
        c.execute("""INSERT INTO checkins VALUES(?,?,?,?) ON CONFLICT(day) DO UPDATE SET
                  energy=COALESCE(excluded.energy,energy),sleep=COALESCE(excluded.sleep,sleep),
                  note=CASE WHEN excluded.note='' THEN note ELSE excluded.note END""",
                  (now().date().isoformat(),*values,note))
    return "✓ Tus respuestas de hoy quedaron guardadas."


def dictate_checkin(path,request:gr.Request):
    guard(request,{"adult"})
    words,status=transcribe(path)
    if not words:
        return gr.skip(),gr.skip(),gr.skip(),status
    numbers={"uno":"1","una":"1","dos":"2","tres":"3","cuatro":"4","cinco":"5"}
    def rating(label):
        match=re.search(r"\b(?:"+label+r")\b[ :,.]*(?:de |un )?([1-5]|uno|una|dos|tres|cuatro|cinco)\b",norm(words))
        if not match:
            return gr.skip()
        return numbers.get(match[1],match[1])
    return words,rating("energia"),rating("descanso|sueno"),"Revisa la transcripción y los valores antes de guardar."


def goal_options():
    return [(f"{g['hh'] or 'Sin hora fija'} · {g['title']}", str(g["id"]))
            for g in scheduled_goals(now().date())]


def load_today_goals(request: gr.Request):
    guard(request, {"adult"})
    return gr.update(choices=goal_options(), value=None)


def save_goal(title,days,hh,request:gr.Request):
    guard(request,{"adult"})
    title,hh=clean(title,100),clean(hh,8)
    if not title or not days or any(d not in DAYS for d in days) or (hh and not TIME_PATTERN.fullmatch(hh)):
        return "Escribe una meta, elige sus días y usa HH:MM si indicas hora.",gr.skip()
    with database() as c:
        c.execute("INSERT INTO goals(title,weekdays,hh,tracked_from) VALUES(?,?,?,?)",
                  (title,",".join(str(DAYS.index(d)) for d in days),hh,now().date().isoformat()))
    return f"Guardé «{title}». La verás en Mi día los días que elegiste.",gr.update(choices=goal_options(),value=None)


def save_outcome(choice,outcome,note,request:gr.Request):
    guard(request,{"adult"})
    gid=extract_id(choice)
    day = now().date()
    goal = next((g for g in scheduled_goals(day) if g["id"] == gid), None)
    if not goal:
        return "Elige una actividad de hoy. Si hiciste algo fuera de tu agenda, abre «Registrar una actividad extra»."
    if outcome not in OUTCOMES:
        return "Elige cómo te fue con esta actividad y vuelve a tocar Guardar."
    with database() as c:
        c.execute("""INSERT INTO goal_log VALUES(?,?,?,?) ON CONFLICT(goal,day)
                    DO UPDATE SET outcome=excluded.outcome,note=excluded.note""",
                  (gid,day.isoformat(),outcome,clean(note,250)))
    return f"Guardé «{goal['title']}» como {outcome.lower()}. Puedes cambiar tu respuesta aquí."


def save_extra_activity(title, note, request: gr.Request):
    guard(request, {"adult"})
    title = clean(title, 100)
    if not title:
        return "Escribe qué hiciste hoy. Por ejemplo, «Jugué dominó».", gr.skip(), gr.skip()
    with database() as c:
        c.execute("""INSERT INTO extra_activities(day,title,note) VALUES(?,?,?)
                     ON CONFLICT(day,title) DO UPDATE SET note=excluded.note""",
                  (now().date().isoformat(), title, clean(note, 250)))
    return f"Guardé «{title}» entre tus actividades extra de hoy.", "", ""


def pref_enabled(name):
    return bool(sql_rows("SELECT 1 FROM preferences WHERE name=? AND enabled=1",(name,)))


def save_prefs(categories,spoken,request:gr.Request):
    guard(request,{"adult"})
    with database() as c:
        c.executemany("INSERT OR REPLACE INTO preferences VALUES(?,?)",
                      [(k,int(k in (categories or []))) for k in SHARE]+[("voz",int(spoken))])
    return "Tus preferencias están guardadas. Se aplican al abrir o actualizar Evolución compartida."


def sharing_preview(categories):
    names = {"Bienestar": "bienestar", "Metas": "actividades", "Horarios": "medicamentos"}
    selected = [names[k] for k in SHARE if k in (categories or [])]
    detail = ("Quien abra el perfil del cuidador verá las gráficas y el detalle por fecha de " + ", ".join(selected) + ".") if selected else "Las tres gráficas quedarán ocultas."
    return ("**Al guardar estos cambios**\n\n" + detail
            + " En **Resumen**, tu cuidador seguirá viendo los horarios, las confirmaciones de hoy "
              "y los movimientos recientes, incluidos los avisos. También conserva acceso al plan, "
              "a tus actividades favoritas y a tu perfil con nombre, zona y contactos. "
              "Bienestar y actividades pueden mostrar tus notas de las fechas consultadas. Tú decides por separado si compartes la cámara.")


def remember_seen(choice,request:gr.Request):
    guard(request,{"adult"})
    mid=extract_id(choice)
    parts=str(choice).split("|")
    hh=parts[1].strip() if len(parts)>1 else ""
    if not any(x["id"]==mid and x["time"]==hh and x["status"]=="pendiente" for x in doses()):
        return "Selecciona un horario pendiente cuya hora ya pasó."
    clock=now()
    with database() as c:
        c.execute("INSERT OR IGNORE INTO seen VALUES(?,?,?,?)",(mid,clock.date().isoformat(),hh,clock.isoformat(timespec="seconds")))
    return "Registraste que viste el aviso. La confirmación de toma se registra por separado."


def slot_in_period(period, day, hh):
    instant = f"{day}T{hh}"
    return period["starts"][:16] <= instant and (not period["ends"] or instant < period["ends"][:16])


def history_slots(start,end, *, read=sql_rows):
    # Reconstruir las oportunidades programadas aun durante una desconexión.
    periods=read("SELECT p.*,m.name FROM plan_period p JOIN medicines m ON m.id=p.med WHERE m.person_id=?", (PERSON_ID,))
    params=(start.isoformat(),end.isoformat())
    confirms={(r["medicine_id"],r["on_date"],r["at_time"]):r["declared_at"] for r in read(
        "SELECT * FROM confirmations WHERE on_date BETWEEN ? AND ?",params)}
    viewed={(r["med"],r["day"],r["hh"]):r["stamp"] for r in read("SELECT * FROM seen WHERE day BETWEEN ? AND ?",params)}
    generated={r["event_key"] for r in read("SELECT event_key FROM events WHERE kind='recordatorio' AND substr(created_at,1,10) BETWEEN ? AND ?",params)}
    rows=[]
    for offset in range((end-start).days+1):
        day=(start+timedelta(days=offset)).isoformat()
        for p in periods:
            for hh in p["hours"].split(","):
                key=(p["med"],day,hh)
                if not slot_in_period(p, day, hh):
                    continue
                rows.append(dict(day=day,hh=hh,med=p["med"],name=p["name"],confirmed=confirms.get(key),
                                 seen=viewed.get(key),generated=f"recordatorio:{p['med']}:{day}:{hh}" in generated))
    return sorted(rows,key=lambda r:(r["day"],r["hh"],r["name"]))


def estimate(slots, *, historical_only=False):
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss
    from collections import defaultdict
    today=now().date().isoformat()
    counts=defaultdict(lambda:[0,0])
    features=[]; labels=[]; dates=[]; base=[]; upcoming=[]
    for day,group in groupby(slots,key=lambda r:r["day"]):
        batch=list(group)
        for r in batch:
            hour=int(r["hh"][:2])
            missed,total=counts[hour]
            rate=(missed+1)/(total+2)
            weekday=date.fromisoformat(day).weekday()
            x=[hour/23, int(weekday>=5), rate]
            if day==today:
                if not r["confirmed"]:
                    upcoming.append((r,x,rate))
            else:
                features.append(x); labels.append(int(not r["confirmed"])); dates.append(day); base.append(rate)
        for r in batch:
            bucket=counts[int(r["hh"][:2])]
            bucket[0]+=int(not r["confirmed"]); bucket[1]+=1
    days=sorted(set(dates))
    if len(days)<28:
        return f"Aprendiendo: {len(days)} de 28 días con horarios históricos. Aún no se calculan estimaciones.",None
    split=dates.index(days[int(len(days)*0.75)])
    if len(set(labels[:split]))<2:
        return "Faltan ejemplos de ambos resultados en el periodo de entrenamiento.",None
    clf=LogisticRegression().fit(features[:split],labels[:split])
    prob=clf.predict_proba(features[split:])[:,1]
    err=brier_score_loss(labels[split:],prob)
    ref=brier_score_loss(labels[split:],base[split:])
    fp=sum(p>=.5 and y==0 for p,y in zip(prob,labels[split:]))
    tp=sum(p>=.5 and y==1 for p,y in zip(prob,labels[split:]))
    message=(f"Evaluación cronológica · {len(labels)-split} horarios posteriores. Error Brier "
             f"(menor es mejor): modelo {err:.3f}, frecuencia por hora {ref:.3f}. "
             f"Con umbral 50 %: {tp} pendientes anticipados y {fp} avisos innecesarios.")
    if historical_only:
        return message, None
    if not upcoming:
        return message+" No quedan horarios por confirmar hoy.",None
    model=clf.fit(features,labels) if err<ref else None
    scored=[(float(model.predict_proba([x])[0,1]) if model else rate,r) for r,x,rate in upcoming]
    p,r=max(scored,key=lambda item:item[0])
    method="regresión logística" if model else "frecuencia histórica por hora"
    return (message+f" Estimación con {method}: {r['hh']} · {p:.0%} de quedar sin confirmación hoy.",
            f"Puedes revisar el horario de las {r['hh']} en tu agenda." if p>=.5 else None)


def read_hint(request:gr.Request):
    guard(request,{"adult"})
    if not pref_enabled("voz"):
        return None,"Activa la sugerencia hablada en tus preferencias."
    day=now().date()
    _,hint=estimate(history_slots(day-timedelta(days=84),day))
    return speak(hint) if hint else (None,"Hoy no hay una sugerencia adicional.")


def weekly_metrics(first, last, checkins, outcomes, slots):
    """Resume periodos de siete días y conserva los huecos de las autodeclaraciones."""
    weeks = []
    start = first
    while start <= last:
        end = min(start + timedelta(days=6), last)
        lo, hi = start.isoformat(), end.isoformat()
        checks = [r for r in checkins if lo <= r["day"] <= hi]
        entries = [r for r in outcomes if lo <= r["day"] <= hi]
        results = [r["outcome"] for r in entries if not r.get("extra")]
        extras = sum(r["outcome"] == "Realizada" and bool(r.get("extra")) for r in entries)
        scheduled = [r for r in slots if lo <= r["day"] <= hi]
        week = {
            "start": start, "end": end, "days": (end-start).days + 1, "checks": len(checks),
            "outcomes": len(entries), "done": results.count("Realizada"), "extras": extras,
            "postponed": results.count("Pospuesta"), "cancelled": results.count("Cancelada"),
            "confirmed": sum(bool(r["confirmed"]) for r in scheduled), "scheduled": len(scheduled),
            "unobserved": sum(not (r["confirmed"] or r["seen"] or r["generated"]) for r in scheduled),
        }
        for field in ("energy", "sleep"):
            readings = [r[field] for r in checks if r[field] is not None]
            week[field] = sum(readings) / len(readings) if readings else None
        weeks.append(week)
        start = end + timedelta(days=1)
    return weeks


def weekly_wellbeing(weeks):
    tramos = [(w["start"], w["end"]) for w in weeks]
    return evolucion.grafica_bienestar(weeks, tramos, diario=False)


def daily_wellbeing(checks, first, last):
    from matplotlib.figure import Figure
    from matplotlib.dates import AutoDateLocator, DateFormatter

    series = pd.DataFrame(checks).set_index("day")
    dates = pd.date_range(first, last)
    series = series.reindex(dates.strftime("%Y-%m-%d"))
    fig = Figure(figsize=(7, 3), layout="constrained")
    ax = fig.subplots()
    ax.plot(dates, series["energy"], marker="o", label="Energía")
    ax.plot(dates, series["sleep"], marker="x", linestyle="--", label="Descanso")
    ax.set(ylim=(0.7, 5.3), yticks=range(1, 6), ylabel="Valor declarado (1 a 5)")
    ax.xaxis.set_major_locator(AutoDateLocator(minticks=3, maxticks=7))
    ax.xaxis.set_major_formatter(DateFormatter("%d/%m"))
    ax.legend()
    return fig


def weekly_table(weeks, allowed):
    headers = ["Semana", "Fechas"]
    if "Bienestar" in allowed:
        headers.extend(["Energía / 5", "Descanso / 5", "Días con chequeo / días del periodo"])
    if "Metas" in allowed:
        headers.extend(["Realizadas de la agenda", "Extras realizadas", "Pospuestas", "Canceladas"])
    if "Horarios" in allowed:
        headers.extend(["Confirmados / programados", "Sin aviso ni declaración registrados"])
    rows = []
    for i, w in enumerate(weeks, 1):
        cells = [str(i), f'{w["start"]:%d/%m} – {w["end"]:%d/%m}']
        if "Bienestar" in allowed:
            cells.extend(f'{w[key]:.1f}' if w[key] is not None else "—" for key in ("energy", "sleep"))
            cells.append(f'{w["checks"]} / {w["days"]}')
        if "Metas" in allowed:
            cells.extend(str(w[key]) if w["outcomes"] else "—" for key in ("done", "extras", "postponed", "cancelled"))
        if "Horarios" in allowed:
            cells.append(f'{w["confirmed"]} / {w["scheduled"]}' if w["scheduled"] else "—")
            cells.append(str(w["unobserved"]) if w["scheduled"] else "—")
        rows.append('<tr><th scope="row">' + cells[0] + '</th>'
                    + ''.join(f"<td>{cell}</td>" for cell in cells[1:]) + '</tr>')
    return ('<div class="weekly-table" tabindex="0" aria-label="Cifras semanales"><table>'
            '<caption>Registros por semana · El guion indica que falta el dato.</caption>'
            '<thead><tr>' + ''.join(f'<th scope="col">{h}</th>' for h in headers)
            + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>')


def demo_end_date(read=sql_rows):
    marker = read("SELECT created_at FROM events WHERE event_key='ana_12_semanas'")
    return date.fromisoformat(marker[0]["created_at"][:10]) - timedelta(days=1) if marker else None


def activity_history(limits, *, read=sql_rows):
    logs = read("""SELECT l.goal AS goal_id,l.day,l.outcome,l.note,g.title,g.weekdays FROM goal_log l JOIN goals g
                       ON g.id=l.goal WHERE l.day BETWEEN ? AND ? ORDER BY l.day,g.hh,g.id""", limits)
    for r in logs:
        r["extra"] = str(date.fromisoformat(r["day"]).weekday()) not in r["weekdays"].split(",")
    logs.extend(read("""SELECT NULL AS goal_id,day,title,note,'Realizada' AS outcome,1 AS extra FROM extra_activities
                            WHERE day BETWEEN ? AND ? ORDER BY day,title""", limits))
    return sorted(logs, key=lambda r:r["day"])


def informe_cuidador(periodo, actividad=evolucion.TODAS, semana="", permisos=None):
    reloj = now()
    hoy = reloj.date()
    with database() as con:
        # Un cambio simultáneo de otro perfil aparece completo en la siguiente actualización.
        con.execute("BEGIN")
        def leer(consulta, parametros=()):
            return [dict(r) for r in con.execute(consulta, parametros)]
        compartidos = {r["name"] for r in leer("SELECT name FROM preferences WHERE enabled=1")}
        permitidos = [k for k in SHARE if k in compartidos and (permisos is None or k in permisos)]
        demo = demo_end_date(leer)
        fijo = periodo == PERIOD_DEMO and demo is not None
        fin = demo if fijo else hoy
        dias = {evolucion.HOY: 1, evolucion.SEMANA: 7}.get(periodo, 84)
        inicio = fin - timedelta(days=dias-1)
        limites = inicio.isoformat(), fin.isoformat()
        nombre = leer("SELECT display_name FROM person WHERE id=?", (PERSON_ID,))[0]["display_name"]
        agenda, chequeos, horarios, para_modelo = [], [], [], []
        if "Metas" in permitidos:
            metas = leer("SELECT id,title,hh,weekdays,tracked_from FROM goals WHERE tracked_from<=? OR tracked_from IS NULL",
                         (limites[1],))
            agenda = evolucion.construir_agenda(metas, activity_history(limites, read=leer), inicio, fin, reloj)
        if "Bienestar" in permitidos:
            chequeos = leer("SELECT * FROM checkins WHERE day BETWEEN ? AND ? ORDER BY day", limites)
        if "Horarios" in permitidos:
            inicio_modelo = inicio if fijo else hoy-timedelta(days=84)
            para_modelo = history_slots(min(inicio, inicio_modelo), fin, read=leer)
            horarios = [r for r in para_modelo if r["day"] >= limites[0]]
    informe = evolucion.informe(nombre, reloj, inicio, fin, permitidos, agenda, chequeos, horarios, actividad, semana)
    if permitidos and fijo:
        informe.encabezado += "<p>Datos ficticios de las 12 semanas de ejemplo. Elige «Hoy» para ver lo que acabas de registrar.</p>"
    modelo = estimate(para_modelo, historical_only=fijo)[0] if "Horarios" in permitidos else ""
    return informe, modelo


def evolution_content(allowed, *, caregiver, period=PERIOD_RECENT):
    if caregiver:
        informe, modelo = informe_cuidador(period, permisos=allowed)
        return informe.encabezado, informe.graficas, informe.detalle, modelo
    if not allowed:
        return "<p>La persona aún no comparte categorías de evolución.</p>", {}, "", ""
    clock = now()
    today = clock.date()
    demo_end = demo_end_date()
    long_demo = demo_end is not None
    fixed = long_demo and period == PERIOD_DEMO
    if fixed:
        last = demo_end
        first = last - timedelta(days=83)
    else:
        last = today
        first = today - timedelta(days=83 if long_demo else today.weekday()+21)
    limits = (first.isoformat(), last.isoformat())
    checks = sql_rows("SELECT * FROM checkins WHERE day BETWEEN ? AND ? ORDER BY day", limits) if "Bienestar" in allowed else []
    logs = activity_history(limits) if "Metas" in allowed else []
    detail_end = last if fixed else today
    slots = history_slots(first if fixed else today-timedelta(days=84), detail_end) if "Horarios" in allowed else []
    observed = [r for r in slots if r["day"] < str(today) or r["hh"] <= clock.strftime("%H:%M") or r["confirmed"]]
    weeks = weekly_metrics(first, last, checks, logs, observed)
    heading = (f'<h3>Evolución de {safe(person()["display_name"])}</h3>'
               f'<p>Del {first:%d/%m/%Y} al {last:%d/%m/%Y} · {len(weeks)} semanas.</p>')
    if fixed:
        heading += "<p>Estás viendo las doce semanas de ejemplo de Ana. Puedes volver a ellas cuando quieras.</p>"
    elif long_demo:
        heading += "<p>Este periodo avanza con el calendario. Para ver el ejemplo original, elige «12 semanas de demostración».</p>"
    figures = {}
    if "Bienestar" in allowed and checks:
        figures["Bienestar"] = weekly_wellbeing(weeks) if long_demo else daily_wellbeing(checks, first, last)

    detail = []
    if long_demo and checks:
        for key, label in (("energy", "Energía"), ("sleep", "Descanso")):
            early = [r[key] for r in checks if r[key] is not None and r["day"] <= weeks[1]["end"].isoformat()]
            late = [r[key] for r in checks if r[key] is not None and r["day"] >= weeks[-2]["start"].isoformat()]
            if early and late:
                detail.append(f"<p>{label} · primeras dos semanas {np.mean(early):.1f}/5"
                              f" · últimas dos {np.mean(late):.1f}/5.</p>")
    detail.append(weekly_table(weeks, allowed))
    if logs:
        detail.append("<h3>Metas recientes</h3>" + "".join(
            f"<p>{r['day']} · {safe(r['title'])}{' (extra)' if r['extra'] else ''} · {safe(r['outcome'])} · {safe(r['note'])}</p>" for r in logs[-5:]))
    if checks:
        detail.extend(f"<p>{r['day']} · {safe(r['note'])}</p>" for r in checks[-5:] if r["note"])
    if slots:
        detail.append(f"<h3>Horarios del {detail_end-timedelta(days=6):%d/%m} al {detail_end:%d/%m}</h3>")
        for r in reversed(observed):
            if r["day"] < str(detail_end-timedelta(days=6)):
                break
            detail.append(f"<p>{r['day']} {r['hh']} · {safe(r['name'])} · "
                          + ("aviso generado" if r["generated"] else "sin aviso generado registrado")
                          + " · " + ("aviso visto "+r["seen"][11:16] if r["seen"] else "sin acuse de vista")
                          + " · " + ("confirmado "+r["confirmed"][11:16] if r["confirmed"] else "sin confirmar") + "</p>")
    model = estimate(slots, historical_only=fixed)[0] if "Horarios" in allowed else ""
    return heading, figures, "".join(detail), model


def evolution_view(request: gr.Request, period=PERIOD_RECENT):
    guard(request, {"adult", "carer"})
    allowed = SHARE if role(request) == "adult" else [k for k in SHARE if pref_enabled(k)]
    heading, figures, detail, model = evolution_content(allowed, caregiver=False, period=period)
    return heading + detail, figures.get("Bienestar"), model


def caregiver_evolution(request: gr.Request, period=PERIOD_DEMO, activity=evolucion.TODAS, week=""):
    guard(request, {"carer"})
    informe, modelo = informe_cuidador(period, activity, week)
    graficas = [gr.update(value=informe.graficas.get(k), visible=informe.graficas.get(k) is not None) for k in SHARE]
    return (informe.encabezado, *graficas, gr.update(value=informe.detalle, visible=bool(informe.detalle)),
            gr.update(value=modelo, visible=bool(modelo)),
            gr.update(choices=informe.actividades, value=informe.actividad if informe.actividades else None,
                      visible="Metas" in informe.graficas and len(informe.actividades) > 1),
            gr.update(choices=informe.semanas, value=informe.semana or None, visible=len(informe.semanas)>1))


def load_shared_evolution(request: gr.Request, period=PERIOD_DEMO, activity=evolucion.TODAS, week=""):
    if role(request) == "carer":
        return caregiver_evolution(request, period, activity, week)
    return (gr.skip(),) * 8


def load_personal(request:gr.Request):
    guard(request,{"adult"})
    return gr.update(choices=goal_options()),[k for k in SHARE if pref_enabled(k)],pref_enabled("voz")


def log_event(kind, detail, key=None):
    with database() as c:
        c.execute("INSERT OR IGNORE INTO events(person_id,kind,event_key,detail,created_at) VALUES(?,?,?,?,?)",
                  (PERSON_ID, kind, key, clean(detail, 350), now().isoformat(timespec="seconds")))


def person():
    return sql_rows("SELECT * FROM person WHERE id=?", (PERSON_ID,))[0]


def set_person(name, zone):
    name, zone = clean(name, 65), clean(zone, 95)
    if not name:
        return "⚠️ Escribe el nombre de pila.", person()["display_name"]
    with database() as c:
        c.execute("UPDATE person SET display_name=?, zone=? WHERE id=?", (name, zone, PERSON_ID))
    log_event("perfil", "Se actualizó el perfil de ejemplo")
    return "✅ Perfil actualizado.", name


def meds():
    return sql_rows("SELECT * FROM medicines WHERE person_id=? AND active=1 ORDER BY name,id", (PERSON_ID,))


def parse_times(raw):
    items = [x.strip() for x in clean(raw, 120).split(",")]
    if not items or len(items) > 8 or any(not TIME_PATTERN.fullmatch(x) for x in items):
        raise ValueError("Utiliza horas separadas por comas, por ejemplo: 08:00, 20:00 (máximo 8).")
    if len(items) != len(set(items)):
        raise ValueError("Cada horario debe ser distinto.")
    return sorted(items)


def add_med(name, instruction, times, notes):
    name, instruction, notes = clean(name, 100), clean(instruction, 200), clean(notes, 250)
    if not name or not instruction:
        return "⚠️ Completa nombre e indicación registrada del profesional."
    try:
        times_clean = parse_times(times)
    except ValueError as e:
        return f"⚠️ {e}"
    with database() as c:
        clock = now()
        cur=c.execute("INSERT INTO medicines(person_id,name,instruction,times,notes) VALUES(?,?,?,?,?)",
                  (PERSON_ID,name,instruction,",".join(times_clean),notes))
        c.execute("INSERT INTO plan_period(med,hours,starts) VALUES(?,?,?)",(cur.lastrowid,",".join(times_clean),clock.isoformat(timespec="minutes")))
    log_event("medicamento", f"Horario registrado para {name}")
    upcoming = [hh for hh in times_clean if hh >= clock.strftime("%H:%M")]
    first = f"hoy a las {upcoming[0]}" if upcoming else f"mañana a las {times_clean[0]}"
    return f"Guardé el plan de {name}. El primer horario en la agenda es {first}."


def remove_med(choice):
    mid = extract_id(choice)
    if mid is None:
        return "⚠️ Elige un medicamento."
    with database() as c:
        r = c.execute("UPDATE medicines SET active=0 WHERE id=? AND person_id=?", (mid,PERSON_ID))
        c.execute("UPDATE plan_period SET ends=? WHERE med=? AND ends IS NULL",(now().isoformat(timespec="minutes"),mid))
    if not r.rowcount:
        return "⚠️ Medicamento no encontrado."
    log_event("medicamento", f"Se desactivó medicamento con ID {mid}")
    return "✅ Horario desactivado. Las confirmaciones anteriores se conservan en el historial."


def extract_id(choice):
    try:
        return int(str(choice).split("|")[0].strip())
    except (ValueError, TypeError):
        return None


def doses(clock=None):
    clock = clock or now()
    date_key = clock.date().isoformat()
    confirmed = {(x["medicine_id"],x["at_time"]):x for x in sql_rows(
        "SELECT medicine_id,at_time,declared_at FROM confirmations WHERE on_date=?",(date_key,))}
    seen = {(r["med"],r["hh"]) for r in sql_rows("SELECT med,hh FROM seen WHERE day=?", (date_key,))}
    result = []
    plans = sql_rows("""SELECT m.id,m.name,m.instruction,p.hours,p.starts,p.ends
                        FROM medicines m JOIN plan_period p ON p.med=m.id
                        WHERE m.person_id=? AND m.active=1""", (PERSON_ID,))
    for m in plans:
        for h in m["hours"].split(","):
            if not slot_in_period(m, date_key, h):
                continue
            conf = confirmed.get((m["id"], h))
            status = "confirmada" if conf else ("pendiente" if h <= clock.strftime("%H:%M") else "proxima")
            result.append({"id":m["id"],"name":m["name"],"instruction":m["instruction"],
                           "time":h,"status":status,"seen":(m["id"],h) in seen,
                           "declared_at":conf["declared_at"] if conf else None})
    return sorted(result,key=lambda x:(x["time"],x["name"]))


def dose_choices():
    return [f'{x["id"]} | {x["time"]} | {x["name"]}' for x in doses() if x["status"]!="confirmada"]


def med_choices():
    return [f'{m["id"]} | {m["name"]} | {m["times"]}' for m in meds()]


def declare_dose(choice, *, expected_day=None, allow_early=False):
    if not choice:
        return "⚠️ Primero selecciona el medicamento y su horario."
    parts = [x.strip() for x in str(choice).split("|")]
    if len(parts) < 2 or extract_id(choice) is None or not TIME_PATTERN.fullmatch(parts[1]):
        return "⚠️ Selección incorrecta."
    mid, hh = int(parts[0]),parts[1]
    with database() as c:
        c.execute("BEGIN IMMEDIATE")
        clock = now()
        day = clock.date().isoformat()
        if expected_day and expected_day != day:
            return "Ya empezó otro día. Abre de nuevo Mis medicamentos para ver la agenda de hoy."
        plan = c.execute("""SELECT m.name,p.hours,p.starts,p.ends FROM medicines m
                            JOIN plan_period p ON p.med=m.id WHERE m.id=? AND m.person_id=? AND m.active=1""",
                         (mid, PERSON_ID)).fetchone()
        if not plan or hh not in plan["hours"].split(",") or not slot_in_period(plan, day, hh):
            return "Ese horario ya no está en tu agenda de hoy. Revisa las tarjetas actualizadas."
        if hh > clock.strftime("%H:%M") and not allow_early:
            return f"El horario de las {hh} es más tarde. Abre «Revisar este horario» para confirmarlo por adelantado."
        name = plan["name"]
        stamp = clock.isoformat(timespec="microseconds")
        saved = c.execute("""INSERT OR IGNORE INTO confirmations(medicine_id,on_date,at_time,declared_at)
                             VALUES(?,?,?,?)""", (mid, day, hh, stamp))
        if not saved.rowcount:
            return f"Ya habías confirmado {name} para las {hh}."
        c.execute("INSERT INTO events(person_id,kind,detail,created_at) VALUES(?,?,?,?)",
                  (PERSON_ID,"toma_declarada",f"Se declaró la toma de {name} para {hh}",stamp))
    return f"Guardé tu confirmación de {name} para las {hh}. Si te equivocaste, toca «Corregir registro»."


def medicine_table():
    return pd.DataFrame([[m["id"],m["name"],m["instruction"],m["times"],m["notes"]] for m in meds()],columns=MED_HEADERS)


def activities():
    return sql_rows("SELECT * FROM activities WHERE person_id=? ORDER BY id DESC", (PERSON_ID,))


def add_activity(name, frequency, notes):
    name, frequency, notes = clean(name,100), clean(frequency,50), clean(notes,200)
    if not name:
        return "⚠️ Escribe una actividad que disfrutes."
    if frequency not in {"Diaria", "Semanal", "Fines de semana", "Ocasional"}:
        return "⚠️ Selecciona una frecuencia válida."
    with database() as c:
        c.execute("INSERT INTO activities(person_id,name,frequency,notes) VALUES(?,?,?,?)",
                  (PERSON_ID,name,frequency,notes))
    log_event("actividad",f"Se registró actividad: {name}")
    return "✅ Actividad favorita guardada."


def activity_table():
    return pd.DataFrame([[a["id"],a["name"],a["frequency"],a["notes"]] for a in activities()],columns=ACT_HEADERS)


def suggest_activities():
    a=activities()
    if not a:
        return "### Ideas para ti\nAgrega alguna actividad que te guste, por ejemplo lectura, música, pintura o jardinería."
    return ("### Actividades que disfrutas\n" + "\n".join(
        f'- **{safe(x["name"])}** · {safe(x["frequency"])}' for x in a[:7]) +
        "\n\n*Son preferencias guardadas; no son eventos confirmados ni recomendaciones médicas.*")


def contacts():
    return sql_rows("SELECT * FROM contacts WHERE person_id=? ORDER BY id DESC", (PERSON_ID,))


def add_contact(name, relationship, phone):
    name, relationship = clean(name,90), clean(relationship,60)
    phone = re.sub(r"\D", "", str(phone or ""))
    if not name or not relationship or not 10 <= len(phone) <= 15:
        return "⚠️ Completa nombre, relación y teléfono internacional de 10 a 15 dígitos."
    with database() as c:
        c.execute("INSERT INTO contacts(person_id,name,relationship,phone) VALUES(?,?,?,?)",
                  (PERSON_ID,name,relationship,phone))
    log_event("contacto","Se agregó un contacto autorizado de demostración")
    return "✅ Contacto guardado. No se ha enviado ningún mensaje."


def contact_table():
    return pd.DataFrame([[x["id"],x["name"],x["relationship"],x["phone"]] for x in contacts()],columns=CONTACT_HEADERS)


def support_links():
    cs = contacts()
    if not cs:
        return "### Pedir apoyo\nNo hay contactos registrados. Ante una emergencia, pide ayuda directa a los servicios locales."
    message="Necesito ayuda y quisiera que te comunicaras conmigo. Mensaje preparado manualmente desde CENTINELA IA (demo)."
    links=["### Contactos de demostración", "Elige un nombre para abrir WhatsApp. Durante el ensayo, deja el mensaje sin enviar."]
    for x in cs:
        u=f'https://wa.me/{x["phone"]}?text={quote(message)}'
        links.append(f'- [{safe(x["name"])} — {safe(x["relationship"])}]({u})')
    return "\n".join(links)


def banner():
    return ('<div class="cent-brand"><div class="cent-mark" aria-hidden="true">👨‍🦳🦉👩‍🦳CENTINELA IA</div>'
            '<div><h1>CENTINELA IA</h1><p>Demo · Versión 2.1</p></div></div>')


def status_tag(status):
    return {"confirmada":'<span class="cent-tag done">✓ Toma confirmada</span>',
            "pendiente":'<span class="cent-tag warning">Por confirmar</span>',
            "proxima":'<span class="cent-tag">Próxima</span>'}[status]


def timeline_html():
    d=doses()
    if not d:
        return '<div class="cent-card"><h3>💊 Mis medicamentos</h3><p>Hoy no tienes horarios vigentes. Tu cuidador puede revisar contigo el plan.</p></div>'
    parts=['<div class="cent-card"><h3>💊 Recordatorios de hoy</h3>']
    previous=None
    for x in d:
        icon,period,_,_=day_part(int(x["time"][:2]))
        if period!=previous:
            parts.append(f'<h4 class="day-section"><span aria-hidden="true">{icon}</span> {period}</h4>')
            previous=period
        parts.append(f'<div class="cent-dose"><div><strong>{friendly_time(x["time"])}</strong> · {safe(x["name"])}'
                     f'<div class="cent-muted">{safe(x["instruction"])}</div></div>{status_tag(x["status"])}</div>')
    parts.append('<p class="cent-muted">Las confirmaciones son declaraciones, no una prueba de ingesta. '
                 'El navegador debe permanecer abierto para ver los cambios en tiempo real.</p></div>')
    return "".join(parts)


MONTHS = ("enero","febrero","marzo","abril","mayo","junio","julio","agosto",
          "septiembre","octubre","noviembre","diciembre")


def day_part(hour):
    if hour < 6:
        return "🌙","Madrugada","Buenas noches","night"
    if hour < 12:
        return "🌅","Mañana","Buenos días","morning"
    if hour < 19:
        return "☀️","Tarde","Buenas tardes","afternoon"
    return "🌙","Noche","Buenas noches","night"


def friendly_time(hh):
    hour,minute=map(int,hh.split(":"))
    if hour==0 and minute==0:
        return "12:00 de la medianoche"
    if hour==12 and minute==0:
        return "12:00 del mediodía"
    return f"{hour % 12 or 12}:{minute:02d} de la {day_part(hour)[1].lower()}"


def day_overview(clock,medications):
    icon,period,greeting,style=day_part(clock.hour)
    day=f"{DAYS[clock.weekday()].lower()} {clock.day} de {MONTHS[clock.month-1]}"
    hh=clock.strftime("%H:%M")
    goals=scheduled_goals(clock.date())
    upcoming=[(m["time"],"Medicamento",m["name"]) for m in medications if m["status"]=="proxima"]
    upcoming.extend((g["hh"],"Actividad",g["title"]) for g in goals if g["hh"] and g["hh"]>=hh and not g["outcome"])
    first=min(upcoming,default=None)
    next_text=(f"{first[1]} · {first[2]} · {friendly_time(first[0])}" if first else "No quedan horarios próximos para hoy.")
    pending=sum(m["status"]=="pendiente" for m in medications)
    pending_text=(f"Tienes {pending} horarios de medicamento por confirmar." if pending>1 else
                  "Tienes un horario de medicamento por confirmar." if pending else "")
    spoken=f"{greeting}, {person()['display_name']}. Hoy es {day}. Son las {friendly_time(hh)}. {next_text}."
    if goals:
        spoken+=" Tus actividades de hoy son: "+". ".join(g["title"] for g in goals)+"."
    visible=(f'<section class="day-now {style}"><span class="day-icon" aria-hidden="true">{icon}</span>'
             f'<div><p>{period} · {day}</p><h2>{greeting}, {safe(person()["display_name"])}</h2>'
             f'<strong>{friendly_time(hh)}</strong></div></section>'
             '<section class="cent-card"><h3>🕒 Lo próximo en mi día</h3>'
             f'<p class="day-next">{safe(next_text,350)}</p>'
             +(f'<p>{pending_text} Abre «Mis medicamentos» para revisarlo.</p>' if pending else '')+'</section>')
    if goals:
        visible+='<section class="cent-card"><h3>⛹️🤸🤾‍♀️ Mis actividades de hoy</h3>'+''.join(
            f'<p><strong>{safe(g["title"])}</strong> · {friendly_time(g["hh"]) if g["hh"] else "Sin hora fija"}'
            +(f' · {safe(g["outcome"])}' if g["outcome"] else '')+'</p>' for g in goals)+'</section>'
    today = clock.date().isoformat()
    extra = [r for r in activity_history((today,today)) if r["extra"] and r["outcome"] == "Realizada"]
    if extra:
        visible += ('<section class="cent-card"><h3>También hice hoy</h3><ul>'
                    + ''.join(f"<li>{safe(r['title'])}</li>" for r in extra) + "</ul></section>")
    return visible,spoken+" "+pending_text


def listen_today(request:gr.Request):
    guard(request,{"adult"})
    clock=now()
    return speak(day_overview(clock,doses(clock))[1])


def summary_html(view="adult"):
    p=person()
    data=doses()
    total=len(data)
    checked=sum(x["status"]=="confirmada" for x in data)
    pending=sum(x["status"]=="pendiente" for x in data)
    if view=="adult":
        return day_overview(now(),data)[0]
    return (f'<div class="cent-hero"><h2>Seguimiento de {safe(p["display_name"])}</h2>'
            '<p>Resumen de declaraciones y actividades registradas. No equivale a vigilancia médica.</p></div>'
            f'<div class="cent-grid"><div class="cent-card"><h3>💊 Confirmaciones de hoy</h3>'
            f'<div class="cent-big">{checked} / {total}</div><p>Confirmadas por declaración de la persona</p></div>'
            f'<div class="cent-card"><h3>🕒 Pendientes</h3><div class="cent-big">{pending}</div>'
            '<p>Sin confirmar según los horarios configurados</p></div></div>')


def event_history():
    rr=sql_rows("SELECT kind,detail,created_at FROM events WHERE person_id=? ORDER BY created_at DESC,id DESC LIMIT 25",(PERSON_ID,))
    if not rr:
        return "Aún no hay movimientos registrados."
    return "### Actividad registrada (últimos 25 eventos)\n"+"\n".join(
        f'- **{safe(x["created_at"].replace("T"," ")[:16])}** · {safe(x["detail"])}' for x in rr)


def process_due(clock=None):
    """Registra recordatorios internos en DB; NO produce mensajes ni llamadas externos.

    Cada hora programada produce su propia clave estable. El proceso necesita
    estar encendido; solo cubre hasta 10 minutos de retraso.
    """
    clock=clock or now()
    count=0
    for x in doses(clock):
        t=datetime.strptime(x["time"],"%H:%M").time()
        scheduled=clock.replace(hour=t.hour,minute=t.minute,second=0,microsecond=0)
        seconds=(clock-scheduled).total_seconds()
        if x["status"]=="pendiente" and 0<=seconds<=600:
            k=f'recordatorio:{x["id"]}:{clock.date().isoformat()}:{x["time"]}'
            with database() as c:
                cur=c.execute("INSERT OR IGNORE INTO events(person_id,kind,event_key,detail,created_at) VALUES(?,?,?,?,?)",
                              (PERSON_ID,"recordatorio",k,f'Horario de {x["name"]} a las {x["time"]}',clock.isoformat(timespec="seconds")))
                count+=int(cur.rowcount)
    return count


def reminder_loop(interface):
    while interface.is_running:
        time.sleep(30)
        if not interface.is_running:
            return
        try:
            process_due()
        except Exception as ex:
            print("No se pudo registrar un recordatorio interno:",type(ex).__name__)


def activity_search(term, zone):
    term, zone=clean(term,100),clean(zone,110)
    if not term or not zone:
        return "⚠️ Escribe una actividad y una zona general autorizada. No introduzcas la dirección de casa."
    query=f"{term} para adultos mayores en {zone}"
    url=f'https://www.google.com/maps/search/?api=1&query={quote_plus(query)}'
    key=os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        return (f'### Buscar lugares\n[Ver resultados de **{safe(query)}** en Google Maps]({url})\n\n'
                '*El prototipo no comprobó lugares ni eventos. Revisa horarios, costo, accesibilidad y disponibilidad.*')
    try:
        res=requests.post("https://places.googleapis.com/v1/places:searchText",
            json={"textQuery":query,"languageCode":"es","regionCode":"MX","pageSize":5},
            headers={"Content-Type":"application/json","X-Goog-Api-Key":key,
                     "X-Goog-FieldMask":"places.displayName,places.formattedAddress,places.googleMapsUri"},timeout=12)
        res.raise_for_status()
        ps=res.json().get("places",[])
    except (requests.RequestException,ValueError):
        return f'⚠️ La búsqueda no respondió. [Buscar manualmente en Maps]({url}).'
    if not ps:
        return f'No aparecieron resultados. [Ver búsqueda manual]({url}).'
    out=["### Lugares encontrados","*Son establecimientos publicados en Google Places, no talleres confirmados. Comprueba horarios, accesibilidad y vigencia.*"]
    for p in ps:
        u=str(p.get("googleMapsUri") or url)
        if not u.startswith("https://"):
            u=url
        out.append(f'- **{safe(p.get("displayName",{}).get("text","Lugar"))}** — '
                   f'{safe(p.get("formattedAddress","Dirección no disponible"))}. [Ver mapa]({u})')
    return "\n".join(out)


def urgent_text():
    return ("Si estás en peligro o necesitas atención inmediata, pide ayuda a alguien cercano. "
            "En México, llama directamente al 911. CENTINELA no llama ni envía alertas por sí solo.")


def message_text(content):
    """Gradio puede entregar texto directo o una lista de bloques de conversación."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(b.get("text", "")) for b in content if isinstance(b, dict) and b.get("type") == "text").strip()
    return ""


def medication_answer(question):
    slots = doses()
    if not slots:
        return "Hoy no aparecen horarios vigentes en tu plan. Puedes revisarlo con tu cuidador."
    if any(word in question for word in ("siguiente", "proxim", "despues", "ahora")):
        remaining = [r for r in slots if r["status"] == "proxima"]
        if remaining:
            hh = remaining[0]["time"]
            names = ", ".join(r["name"] for r in remaining if r["time"] == hh)
            return f"El siguiente horario de tu agenda es a las {hh} para {names}. Puedes verlo en Mis medicamentos."
        return "Hoy ya pasaron los horarios programados. En Mis medicamentos puedes revisar cuáles confirmaste."
    if "pendient" in question or "falta" in question:
        slots = [r for r in slots if r["status"] == "pendiente"]
        if not slots:
            return "Hasta esta hora, todos tus horarios transcurridos están al día en el registro."
    status = {"confirmada":"ya lo confirmaste", "pendiente":"por confirmar", "proxima":"más tarde"}
    lines = [f"{r['time']}, {r['name']} ({status[r['status']]})" for r in slots]
    return "En tu plan de hoy aparecen estos horarios. " + ". ".join(lines) + "."


def assistant_answer(message, history=None, *, use_openai=False):
    """Responds to a typed or transcribed message, respecting safety constraints.

    An OpenAI key is optional: common daily-life questions work without it.
    """
    msg=clean(message,900)
    history=list(history or [])
    t=norm(msg)
    if any(x in t for x in ("me cai","me he caido","no me puedo levantar","dolor en el pecho","me falta el aire","emergencia","auxilio")):
        return urgent_text()
    pide_diagnostico = re.search(r"\b(diagnostico|diagnosticar\w*|diagnostica\w*|recetame|recetarme)\b", t)
    cambio_de_toma = (re.search(r"\b(dosis|medicamento\w*|medicina\w*|pastilla\w*|tratamiento\w*|toma)\b", t)
                      and re.search(r"\b(duplic\w*|dobl\w*|aument\w*|reduci\w*|suspend\w*|olvid\w*|cambi\w*)\b", t))
    if pide_diagnostico or cambio_de_toma:
        return ("Puedo mostrarte los horarios que ya están guardados. Para un diagnóstico, una dosis olvidada "
                "o un cambio de tratamiento, consulta al profesional que te atiende.")
    if any(x in t for x in ("ya lo tome","ya me la tome","ya la tome","ya me lo tome","ya tome")):
        return ("Abre Mis medicamentos y busca el nombre y la hora. Si ese horario ya pasó, toca Ya lo tomé. "
                "Si es más tarde, toca Revisar este horario.")
    mentions_med = re.search(r"\b(medicamentos?|medicinas?|pastillas?|tabletas?|dosis|tratamientos?|tomas?)\b", t)
    asks_to_take = re.search(r"\b(que (?:tengo|debo|me toca|hay) (?:que )?tomar|que tomo|a que hora (?:tomo|me toca)|que me toca tomar)\b", t)
    if mentions_med or (asks_to_take and not any(w in t for w in ("agua", "cafe", "bebida"))):
        return medication_answer(t)
    if "hoy" in t and any(x in t for x in ("actividad","agenda","meta","que tengo","que hago")):
        agenda = today_agenda()
        return ("Hoy tienes estas actividades. " + ". ".join(agenda) + ".") if agenda else "Hoy tienes la agenda de actividades libre."
    if any(x in t for x in ("cerca","lugares","parque","centro cultural","taller")):
        return ("En «Actividades» puedes buscar lugares de una zona general que autorices. "
                "Antes de asistir, confirma la actividad, el horario y su accesibilidad.")
    if any(x in t for x in ("actividad","aburro","pintar","pintura","caminar","lectura","musica","pasatiempo")):
        a=activities()
        if a:
            return ("Tienes estas actividades favoritas registradas: "+
                    ", ".join(x["name"] for x in a[:5])+
                    ". ¿Cuál te gustaría disfrutar hoy? Podemos organizarla a tu ritmo.")
        return ("Podemos registrar tus gustos, como música, lectura o pintura. "
                "¿Qué actividad disfrutas más? Puedes añadirla en «Actividades».")
    if any(x in t for x in ("hola","buenos dias","buenas tardes","buenas noches")):
        return (f'¡Hola, {person()["display_name"]}! Qué gusto escucharte. '
                "¿Te gustaría hablar, revisar tus horarios o pensar en una actividad agradable?")
    if any(x in t for x in ("gracias","muchas gracias")):
        return "Con gusto. Estoy aquí para acompañarte. ¿Hay algo más que quieras compartir?"
    if any(x in t for x in ("como estas","como te va","que haces")):
        return "Estoy disponible para conversar contigo. ¿Cómo te sientes hoy?"
    if any(x in t for x in ("solo","sola","triste","platicar","conversar","charlar","hablar contigo")):
        return ("Me gusta que quieras conversar. Si te apetece, cuéntame algo que te haya "
                "hecho sonreír hoy. También puedes contactar a alguien de confianza.")
    if any(x in t for x in ("que dia","que fecha","que hora","hoy es")):
        return f'En la zona horaria configurada son las {now():%H:%M} del {now():%d/%m/%Y}.'
    if any(x in t for x in ("ayuda","contacto","familia","hija","hijo","cuidador")):
        return ("Puedes consultar los contactos registrados en la sección de ayuda. "
                "Este prototipo no realiza llamadas ni envía mensajes automáticamente.")
    key=os.getenv("OPENAI_API_KEY","").strip()
    if use_openai and key:
        try:
            from openai import OpenAI
            cliente=OpenAI(api_key=key,timeout=22)
            conversation=[]
            for item in history[-8:]:
                if isinstance(item,dict) and item.get("role") in ("user","assistant"):
                    words = message_text(item.get("content"))
                    if words:
                        conversation.append({"role":item["role"],"content":clean(words,1000)})
            conversation.append({"role":"user","content":msg})
            reply=cliente.responses.create(
                model=os.getenv("OPENAI_CHAT_MODEL","gpt-4.1-mini"),
                instructions=("Eres CENTINELA IA, asistente de compañía de un prototipo para personas mayores. "
                  "Conversa en español de México, lenguaje sencillo y cálido; máximo 90 palabras por respuesta. "
                  "Responde al último mensaje teniendo en cuenta el breve historial proporcionado. "
                  "No diagnostiques, recetes ni cambies medicamentos. No inventes recordatorios ni consultas "
                  "con sistemas externos. Nunca afirmes que llamaste a un familiar, ni que supervisas la cámara. "
                  "Si hay urgencia médica, recomienda solicitar ayuda humana inmediata."),
                input=conversation,max_output_tokens=230,store=False)
            return (reply.output_text or "").strip() or "¿Quieres contarme un poco más?"
        except Exception:
            logging.exception("CENTINELA: fallo del servicio conversacional")
            return ("La conversación avanzada no está disponible en este momento. "
                    "Podemos conversar sobre tus intereses, horarios o actividades.")
    # Real interaction even without an external API key.
    if len(history)>=2 and t in ("si","claro","vale","por favor"):
        return ("¡Qué bien! Cuéntame un poco más sobre lo que te gustaría hacer, "
                "o pregúntame por tus medicamentos y actividades.")
    return ("Te escucho. ¿Qué te gustaría contarme? También puedo ayudarte con "
            "tu agenda de medicamentos, actividades favoritas y lugares cercanos.")


def chat_reply(message, history, *, use_openai=False):
    msg=clean(message,900)
    history=list(history or [])
    if not msg:
        return history,"","Escribe un mensaje o graba una nota de voz."
    reply=assistant_answer(msg,history,use_openai=use_openai)
    history.extend([{"role":"user","content":msg},{"role":"assistant","content":reply}])
    return history,"",reply


WHISPER=None
WHISPER_LOCK=threading.Lock()


def transcribe(path):
    if not path:
        return "", "No llegó una grabación. Abre el enlace de Gradio en su propia pestaña, permite el micrófono y pulsa Grabar."
    try:
        from faster_whisper.audio import decode_audio
        samples=decode_audio(str(path),sampling_rate=16000)
    except Exception:
        logging.exception("No se pudo abrir el archivo de audio")
        return "", "No pude abrir ese audio. Vuelve a grabar o sube un archivo WAV o MP3."
    if len(samples)<4800:
        return "", "La grabación dura menos de un tercio de segundo. Espera a ver el contador, habla y pulsa Detener."
    if len(samples)>16000*90:
        return "", "Graba un mensaje de hasta 90 segundos."
    peak=float(np.max(np.abs(samples)))
    if not np.isfinite(peak) or peak<0.001:
        return "", "No escuché tu voz. Revisa el micrófono y toca Empezar a hablar para probar otra vez."
    # Compensar una voz suave sin amplificar en exceso el ruido de fondo.
    samples=samples*min(6,0.85/peak)
    global WHISPER
    with WHISPER_LOCK:
        if WHISPER is None:
            try:
                from faster_whisper import WhisperModel
                size=os.getenv("CENTINELA_WHISPER_MODEL","tiny")
                WHISPER=WhisperModel(size if size in ("tiny","base","small") else "tiny",device="cpu",compute_type="int8")
            except Exception:
                logging.exception("Carga de Whisper")
                return "", "Recibí el audio, pero no pude cargar Whisper. Comprueba la conexión de Colab y repite la prueba de voz."
        try:
            segments,_=WHISPER.transcribe(samples,language="es",beam_size=3,vad_filter=True,
                         vad_parameters={"min_silence_duration_ms":500,"speech_pad_ms":220},
                         condition_on_previous_text=False)
            text=" ".join(s.text.strip() for s in segments).strip()
        except Exception:
            logging.exception("Transcripción")
            return "", "Recibí la grabación, pero falló el reconocimiento. Usa la prueba de voz del cuaderno para revisar la instalación."
    if not text:
        return "", "No distinguí palabras. Acerca el micrófono y toca Empezar a hablar para intentarlo de nuevo."
    return clean(text,900),"Audio transcrito. Puedes revisar el texto."


def process_audio(path, history, previous, request, *, retry=False, browser_audio=None, use_openai=False, google_voice=False):
    import hashlib
    guard(request, {"adult"})
    previous = previous if isinstance(previous, dict) else {}
    if not path:
        yield gr.skip(),gr.skip(),gr.skip(),"","Primero graba un mensaje o elige un archivo de audio.",None,"",None
        return
    with open(path, "rb") as audio_file:
        key = hashlib.sha256(audio_file.read()).hexdigest()
    same = key == previous.get("key")
    if same and previous.get("text") and not retry:
        yield (gr.skip(),) * 8
        return
    state = dict(previous) if same else {"key": key}
    state["browser_audio"] = browser_audio
    progress = "Vuelvo a escuchar tu grabación…" if retry else "Te escuché. Estoy pasando tu mensaje a texto…"
    yield gr.skip(),gr.skip(),gr.skip(),gr.skip(),progress,None,"",state
    words, status = transcribe(path)
    if not words:
        yield gr.skip(),gr.skip(),gr.skip(),gr.skip(),status,None,"",state
        return
    history = list(history or [])
    if same and words == state.get("text") and state.get("answer"):
        updated, answer = history, state["answer"]
    else:
        if same and len(history) >= 2 and [message_text(m.get("content")) for m in history[-2:]] == [state.get("text"), state.get("answer")]:
            history = history[:-2]
        updated, _, answer = chat_reply(words, history, use_openai=use_openai)
    state = dict(state, text=words, answer=answer)
    complete = "Listo. Volví a transcribir tu grabación." if retry else "Listo. Esto es lo que entendí."
    yield updated,"",answer,words,complete,None,"Preparando la respuesta en voz alta…",state
    audio, message = speak(answer, google_voice=google_voice)
    yield gr.skip(),gr.skip(),gr.skip(),gr.skip(),gr.skip(),audio,message,state


def handle_recording(path, history, previous, request: gr.Request, use_openai=False, google_voice=False):
    yield from process_audio(path, history, previous, request, use_openai=use_openai, google_voice=google_voice)


def retry_recording(path, history, previous, request: gr.Request, use_openai=False, google_voice=False):
    payload = previous.get("browser_audio") if isinstance(previous, dict) else None
    if payload:
        yield from process_browser_audio(payload, history, previous, request, retry=True, use_openai=use_openai, google_voice=google_voice)
    else:
        yield from process_audio(path, history, previous, request, retry=True, use_openai=use_openai, google_voice=google_voice)


def voice_preferences():
    defaults = voces.VOZ_INICIAL, voces.RITMO_INICIAL
    if not DB_PATH.is_file():
        return defaults
    try:
        rows = sql_rows("SELECT voice_id, pace FROM voice_preferences WHERE person_id=?", (PERSON_ID,))
    except sqlite3.OperationalError as exc:
        if "no such table: voice_preferences" in str(exc):
            return defaults
        raise
    if not rows:
        return defaults
    voice, pace = rows[0]["voice_id"], rows[0]["pace"]
    return (voice if voice in voces.VOCES else defaults[0],
            pace if pace in voces.RITMOS else defaults[1])


def current_voice_label(voice, pace):
    return f"Tu voz guardada es **{voces.VOCES[voice].etiqueta}**, con ritmo **{voces.RITMOS[pace][0].lower()}**."


def load_voice_controls(request: gr.Request):
    guard(request, {"adult"})
    voice, pace = voice_preferences()
    return voice, pace, current_voice_label(voice, pace), gr.update(value=None, visible=False)


def check_voice_choice(voice, pace):
    if voice not in voces.VOCES or pace not in voces.RITMOS:
        raise gr.Error("Elige una voz y un ritmo de la lista.")


def preview_voice(voice, pace, request: gr.Request):
    guard(request, {"adult"})
    check_voice_choice(voice, pace)
    sample = voces.AUDIOS / f"muestra_{voice}_{pace}.mp3"
    return gr.update(value=sample.read_bytes(), visible=True,
                     label=f"Muestra de {voces.VOCES[voice].nombre} · ritmo {voces.RITMOS[pace][0].lower()}")


def save_voice(voice, pace, request: gr.Request):
    guard(request, {"adult"})
    check_voice_choice(voice, pace)
    with database() as db:
        db.execute("""INSERT INTO voice_preferences(person_id, voice_id, pace) VALUES(?, ?, ?)
                      ON CONFLICT(person_id) DO UPDATE SET voice_id=excluded.voice_id, pace=excluded.pace""",
                   (PERSON_ID, voice, pace))
    return current_voice_label(voice, pace), avisos.aviso_html(voice, pace), gr.update(value=None, visible=False), False


def speak(text, *, google_voice=False):
    """Usa la elección del perfil o la voz externa solicitada para el chat de esta visita."""
    import shutil
    import subprocess

    text = clean(text, 800)
    if not text:
        return None, "Escribe un mensaje o usa el audio de ejemplo."
    voice, pace = voice_preferences()
    name = voces.VOCES[voice].nombre
    if google_voice:
        try:
            from gtts import gTTS
            output = io.BytesIO()
            gTTS(voces.para_leer(text), lang="es", tld="com.mx", slow=pace=="pausado", timeout=6).write_to_fp(output)
            return output.getvalue(), "Lectura con la voz de Google que elegiste para este chat."
        except Exception:
            logging.warning("El servicio de voz opcional no respondió.")
    try:
        audio = voces.sintetizar(text, voice, pace)
        estado = f"Lectura con {name}, a ritmo {voces.RITMOS[pace][0].lower()}."
        return audio, ("Google no respondió. " if google_voice else "") + estado
    except Exception as exc:
        logging.warning("Voz del entorno no disponible (%s, %s).", voice, type(exc).__name__)
    engine = shutil.which("espeak-ng") or shutil.which("espeak")
    if engine:
        try:
            with tempfile.TemporaryDirectory() as directory:
                output_path = Path(directory) / "respuesta.wav"
                speed = str(round(145 * voces.RITMOS[pace][1]))
                subprocess.run([engine, "-v", "es", "-s", speed, "-w", str(output_path), "--stdin"],
                               input=voces.para_leer(text).encode("utf-8"), capture_output=True, check=True, timeout=20)
                return output_path.read_bytes(), f"Lectura con la voz básica. Para recuperar {name}, repite «Preparar las voces» en el cuaderno."
        except (OSError, subprocess.SubprocessError):
            logging.warning("El motor de voz básico no está disponible.")
    return None, f"Puedes leer la respuesta. Para escuchar a {name}, repite «Preparar las voces» en el cuaderno."


class CameraRelay:
    """Relé de fotogramas efímeros para UNA persona, sin grabación intencional.

    No es WebRTC ni un servicio de producción. Por seguridad, una sesión adulta
    debe autorizar explícitamente el envío; otra sesión no puede publicar cuadros.
    Un cuadro deja de mostrarse a los pocos segundos y el permiso caduca si se
    interrumpe la captura. Los datos NO se escriben a la base SQLite.
    """
    FRAME_TTL = 6.0
    STREAM_TIMEOUT = 25.0

    def __init__(self):
        self._lock = threading.RLock()
        self.active = False
        self.owner = None
        self.started_at = 0.0
        self.latest = None
        self.last_frame = 0.0
        self.frames = 0
        self.generation = 0

    def start(self, session: str):
        if not session:
            raise ValueError("Abre el perfil de la persona en una pestaña de la demostración.")
        with self._lock:
            self.generation += 1
            self.active = True
            self.owner = str(session)
            self.started_at = time.monotonic()
            self.latest = None
            self.last_frame = 0.0
            self.frames = 0

    def stop(self):
        with self._lock:
            was_active = self.active
            self.active = False
            self.owner = None
            self.latest = None
            self.last_frame = 0.0
            self.started_at = 0.0
            self.frames = 0
            return was_active

    def stop_if_owner(self, session: str) -> bool:
        """Revoca inmediatamente solo la transmisión de la sesión indicada."""
        with self._lock:
            if not self.active or self.owner != session:
                return False
            return self.stop()

    def _expire_if_idle(self, clock):
        if self.active and clock - (self.last_frame or self.started_at) >= self.STREAM_TIMEOUT:
            self.stop()

    def owns_active_camera(self, session):
        with self._lock:
            self._expire_if_idle(time.monotonic())
            return self.active and self.owner == session

    def publish(self, frame, session: str):
        with self._lock:
            self._expire_if_idle(time.monotonic())
            if not self.active or self.owner != session:
                return False
            generation = self.generation
        if frame is None:
            return False
        try:
            from PIL import Image
            arr = np.asarray(frame)
            if arr.ndim not in (2, 3) or arr.shape[0] < 1 or arr.shape[1] < 1:
                return False
            if arr.ndim == 3 and arr.shape[2] not in (3, 4):
                return False
            img = Image.fromarray(arr.astype(np.uint8)).convert("RGB")
            img.thumbnail((640, 480))
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=60, optimize=True)
            data = output.getvalue()
            if len(data) > 180_000:
                return False
        except (ValueError, TypeError, OSError):
            return False
        with self._lock:
            clock = time.monotonic()
            self._expire_if_idle(clock)
            if not self.active or self.owner != session or self.generation != generation:
                return False
            self.latest = data
            self.last_frame = clock
            self.frames += 1
            return True

    def snapshot(self, clock=None):
        t = time.monotonic() if clock is None else clock
        with self._lock:
            self._expire_if_idle(t)
            if not self.active:
                return "off", None, None
            if self.latest is None:
                return "connecting", None, None
            age = max(0.0, t - self.last_frame)
            if age > self.FRAME_TTL:
                return "stale", None, age
            return "live", self.latest, age


CAMERA_RELAY = CameraRelay()


def video_placeholder(title, note):
    return (f'<div class="cent-video-shell"><div class="cent-video-placeholder">'
            f'📹<strong>{html.escape(title)}</strong>{html.escape(note)}</div></div>')


def video_markup(state, frame):
    if state == "live" and frame:
        encoded = base64.b64encode(frame).decode("ascii")
        # Imagen incrustada: no se crea una URL de archivo descargable del lado de Gradio.
        return ('<div class="cent-video-shell"><img alt="Cámara de demostración autorizada: sala" '
                f'src="data:image/jpeg;base64,{encoded}" /></div>')
    labels = {
        "off": ("Cámara apagada", "La persona no está compartiendo imágenes."),
        "connecting": ("Esperando cámara", "La persona debe permitir la webcam en su navegador e iniciarla."),
        "stale": ("Señal interrumpida", "No hay imágenes recientes; no se puede conocer el estado de la persona."),
    }
    return video_placeholder(*(labels.get(state, labels["off"])))


def session_for_camera(request):
    sid = getattr(request, "session_hash", None)
    if not sid:
        raise gr.Error("No se pudo confirmar la sesión. Recarga la página e inténtalo de nuevo.")
    return str(sid)


def adult_camera_start(request: gr.Request):
    # El cambio de perfil y el inicio de la cámara deben respetar el mismo orden.
    with PROFILE_LOCK:
        guard(request, {"adult"})
        CAMERA_RELAY.start(session_for_camera(request))
    log_event("camara", "La persona habilitó compartir cámara (demostración)")
    return (gr.update(visible=True),
            "✅ **Compartir habilitado.** Inicia la cámara en el cuadro inferior y concede el permiso del navegador. "
            "Quien entre al perfil del cuidador podrá verla mientras la compartas. "
            "Para detener el envío pulsa **Dejar de compartir**.", gr.update(active=True))


def adult_camera_frame(frame, request: gr.Request):
    guard(request, {"adult"})
    owner = session_for_camera(request)
    if frame is None:
        return "Esperando imágenes. Comprueba que la webcam esté encendida."
    if CAMERA_RELAY.publish(frame, owner):
        return "🟢 Estás compartiendo imágenes sin audio con el perfil del cuidador."
    return "Si la señal se interrumpió, toca «Compartir cámara con mi cuidador» para dar permiso otra vez."


def check_adult_camera(request: gr.Request):
    guard(request, {"adult"})
    if CAMERA_RELAY.owns_active_camera(session_for_camera(request)):
        return gr.skip(), gr.skip(), gr.skip()
    return (gr.update(visible=False,value=None),
            "La cámara quedó apagada. Si quieres volver a compartirla, toca «Compartir cámara con mi cuidador».",
            gr.update(active=False))


def adult_camera_stop(request: gr.Request):
    guard(request, {"adult"})
    if CAMERA_RELAY.stop_if_owner(session_for_camera(request)):
        log_event("camara", "La persona detuvo compartir cámara (demostración)")
    return (gr.update(visible=False, value=None),
            "🔒 Dejaste de compartir la cámara. Puedes volver a activarla cuando quieras.", gr.update(active=False))


def caregiver_open_video(request: gr.Request):
    guard(request, {"carer"})
    log_event("camara", "El cuidador abrió la vista remota de demostración")
    state, frame, age = CAMERA_RELAY.snapshot()
    return True, video_markup(state, frame), video_status(state, age), gr.update(active=True)


def video_status(state, age):
    if state == "live":
        return f"🟢 **Señal reciente ({age:.1f} s).** Fotogramas de baja frecuencia; no es vigilancia clínica."
    if state == "connecting":
        return "🟡 Cámara habilitada, pero todavía no llegan imágenes."
    if state == "stale":
        return "⚠️ **Señal interrumpida.** No se debe asumir que la persona está bien."
    return "🔒 Cámara apagada por la persona o por desconexión. No hay video disponible."


def caregiver_poll_video(watching: bool, request: gr.Request):
    guard(request, {"carer"})
    if not watching:
        return video_placeholder("Vista cerrada", "Pulsa Ver cámara para empezar."), "La visualización está desactivada."
    state, frame, age = CAMERA_RELAY.snapshot()
    return video_markup(state, frame), video_status(state, age)


def caregiver_close_video(request: gr.Request):
    guard(request, {"carer"})
    log_event("camara", "El cuidador cerró la vista remota de demostración")
    return (False, video_placeholder("Vista cerrada", "Pulsa Ver cámara para empezar."),
            "🔒 Dejaste de ver la cámara.", gr.update(active=False))


# Gradio asigna una session_hash a cada pestaña. La elección se guarda en memoria
# solo durante esa visita; los registros de la demostración se guardan en SQLite.
PROFILE_LOCK = threading.RLock()
VISIT_PROFILES = {}


def role(request):
    with PROFILE_LOCK:
        return VISIT_PROFILES.get(getattr(request, "session_hash", None))


def enter_demo(profile, request: gr.Request):
    sid = getattr(request, "session_hash", None)
    if not sid or profile not in {"adult", "carer"}:
        raise gr.Error("Vuelve a la portada y elige uno de los dos perfiles.")
    with PROFILE_LOCK:
        previous = VISIT_PROFILES.get(sid)
        if previous is not None and previous != profile:
            raise gr.Error("Usa Cambiar de perfil para volver a la portada.")
        VISIT_PROFILES[sid] = profile
        try:
            panels = initial_view(request)
        except Exception:
            if previous is None:
                VISIT_PROFILES.pop(sid, None)
            raise
    return (gr.update(visible=False), *panels)


def leave_demo(request: gr.Request):
    sid = getattr(request, "session_hash", None)
    if not sid:
        return
    with PROFILE_LOCK:
        previous = VISIT_PROFILES.pop(sid, None)
        stopped = CAMERA_RELAY.stop_if_owner(sid)
    if stopped:
        log_event("camara", "La persona dejó de compartir la cámara al salir de su perfil.")
    if previous:
        label = "la persona" if previous == "adult" else "el cuidador"
        log_event("sesion", f"Terminó la visita de {label} a su perfil de demostración.")


# Recargar desmonta la interfaz anterior y limpia el chat, los audios y los
# temporizadores de esa pestaña. La nueva visita siempre comienza en la portada.
RETURN_TO_PROFILES_JS = """() => {
    const recorder = window.centinelaRecorder;
    if (recorder && recorder.state === "recording") {
        recorder.cancelled = true;
        recorder.stop();
    }
    if (recorder?.stream) recorder.stream.getTracks().forEach(track => track.stop());
    document.querySelectorAll("video, audio").forEach(el => {
        el.pause();
        if (el.srcObject?.getTracks) el.srcObject.getTracks().forEach(track => track.stop());
    });
    if ("scrollRestoration" in window.history) window.history.scrollRestoration = "manual";
    window.scrollTo(0, 0);
    window.location.reload();
}"""


def guard(request, permitted):
    if role(request) not in permitted:
        raise gr.Error("Esta opción está en el otro perfil. Puedes elegirlo desde la portada.")


def initial_view(request:gr.Request):
    """Cargar los datos del perfil seleccionado en esta pestaña."""
    r=role(request)
    visible=(gr.update(visible=r=="adult"),gr.update(visible=r=="carer"))
    timers=(gr.update(active=r=="adult"),gr.update(active=r=="carer"))
    empty_table=lambda columns:pd.DataFrame(columns=columns)
    if r=="adult":
        return (*visible, summary_html("adult"), timeline_html(),
                gr.update(choices=dose_choices(),value=None), suggest_activities(), support_links(),
                "", "", empty_table(MED_HEADERS), gr.update(choices=[],value=None),
                empty_table(ACT_HEADERS), empty_table(CONTACT_HEADERS), "", "", "", *timers)
    if r=="carer":
        p=person()
        return (*visible,"","",gr.update(choices=[],value=None),"","",
                summary_html("carer"),timeline_html(),medicine_table(),
                gr.update(choices=med_choices(),value=None),activity_table(),contact_table(),
                event_history(),p["display_name"],p["zone"],*timers)
    raise gr.Error("Primero elige un perfil en la portada.")


def refresh_adult(selection,request:gr.Request):
    guard(request,{"adult"})
    process_due()
    choices=dose_choices()
    return summary_html("adult"),timeline_html(),gr.update(choices=choices,value=selection if selection in choices else None),suggest_activities(),support_links()


def refresh_carer(request:gr.Request):
    guard(request,{"carer"})
    process_due()
    return (summary_html("carer"),timeline_html(),medicine_table(),
            gr.update(choices=med_choices(),value=None),activity_table(),contact_table(),event_history())


def adult_confirm(choice,request:gr.Request):
    guard(request,{"adult"})
    msg=declare_dose(choice)
    return msg,summary_html("adult"),timeline_html(),gr.update(choices=dose_choices(),value=None)


def carer_add_med(name,ind,times,notes,request:gr.Request):
    guard(request,{"carer"})
    msg=add_med(name,ind,times,notes)
    return msg,medicine_table(),gr.update(choices=med_choices(),value=None),timeline_html(),summary_html("carer")


def carer_remove_med(choice,request:gr.Request):
    guard(request,{"carer"})
    msg=remove_med(choice)
    return msg,medicine_table(),gr.update(choices=med_choices(),value=None),timeline_html(),summary_html("carer")


def adult_add_activity(name,frequency,notes,request:gr.Request):
    guard(request,{"adult"})
    msg=add_activity(name,frequency,notes)
    return msg,suggest_activities(),summary_html("adult")


def carer_add_activity(name,frequency,notes,request:gr.Request):
    guard(request,{"carer"})
    msg=add_activity(name,frequency,notes)
    return msg,activity_table()


def carer_add_contact(name,relationship,phone,request:gr.Request):
    guard(request,{"carer"})
    msg=add_contact(name,relationship,phone)
    return msg,contact_table(),support_links()


def carer_set_profile(name,zone,request:gr.Request):
    guard(request,{"carer"})
    msg,_=set_person(name,zone)
    return msg,summary_html("carer")


def adult_places(term,zone,request:gr.Request):
    guard(request,{"adult"})
    return activity_search(term,zone)


def adult_chat(msg,history,request:gr.Request,use_openai=False):
    guard(request,{"adult"})
    return chat_reply(msg,history,use_openai=use_openai)


def adult_transcribe(path,request:gr.Request):
    guard(request,{"adult"})
    return transcribe(path)


def adult_speak(message,request:gr.Request,google_voice=False):
    guard(request,{"adult"})
    return speak(message, google_voice=google_voice)


def process_browser_audio(payload, history, previous, request, *, retry=False, use_openai=False, google_voice=False):
    guard(request, {"adult"})
    if not payload:
        yield (gr.skip(),) * 8
        return
    try:
        if not payload.startswith("data:audio/") or len(payload) > 12000000:
            raise ValueError("Formato o tamaño de audio")
        raw = base64.b64decode(payload.split(",", 1)[1], validate=True)
    except (ValueError, IndexError):
        yield gr.skip(),gr.skip(),gr.skip(),gr.skip(),"Esta grabación no se pudo abrir. Puedes grabar otra o elegir un archivo.",None,"",gr.skip()
        return
    with tempfile.NamedTemporaryFile(suffix=".audio") as buf:
        buf.write(raw)
        buf.flush()
        yield from process_audio(buf.name, history, previous, request, retry=retry, browser_audio=payload,
                                 use_openai=use_openai, google_voice=google_voice)


def record_from_browser(payload, history, previous, request: gr.Request, use_openai=False, google_voice=False):
    yield from process_browser_audio(payload, history, previous, request, use_openai=use_openai, google_voice=google_voice)


RECORD_JS = """async () => {
 const host=document.querySelector('#single-mic');
 const button=host.matches('button')?host:host.querySelector('button');
 const message=document.querySelector('#mic-feedback');
 const say=t=>{if(message) message.textContent=t;};
 const current=window.centinelaRecorder;
 if(current && current.state==='recording'){
   current.stop(); return await current.result;
 }
 if(window.centinelaGettingMic) return '';
 window.centinelaGettingMic=true;
 let stream;
 try {
   stream=await navigator.mediaDevices.getUserMedia({audio:true});
   const rec=new MediaRecorder(stream); const chunks=[];
   window.centinelaRecorder=rec;
   rec.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
   rec.result=new Promise(resolve=>{
     rec.onstop=()=>{
       clearTimeout(rec.limit); stream.getTracks().forEach(t=>t.stop());
       button.textContent='🎙️ Empezar a hablar'; window.centinelaRecorder=null;
       if(rec.cancelled){say('Micrófono apagado.');resolve('');return;}
       const reader=new FileReader();
       reader.onload=()=>resolve(reader.result); reader.onerror=()=>resolve('');
       reader.readAsDataURL(new Blob(chunks,{type:rec.mimeType || 'audio/webm'}));
       say('Grabación terminada.');
     };
   });
   rec.start(); button.textContent='⏹️ Terminé de hablar'; say('Te escucho. Cuando termines, toca el mismo botón.');
   rec.limit=setTimeout(()=>{if(rec.state==='recording')button.click();},85000);
   const cancel=()=>{if(rec.state==='recording'){rec.cancelled=true;rec.stop();}};
   const monitor=setInterval(()=>{if(rec.state==='inactive'){clearInterval(monitor);return;}if(!button.getClientRects().length)cancel();},350);
   window.addEventListener('pagehide',cancel,{once:true});
 } catch(e){if(stream)stream.getTracks().forEach(t=>t.stop());say('El micrófono está apagado. Puedes escribir en «Mi mensaje» o usar la voz de ejemplo.');}
 finally {window.centinelaGettingMic=false;}
 return '';
}"""


def medicine_cards(request:gr.Request):
    guard(request,{"adult"})
    clock=now()
    return [dict(d,day=str(clock.date())) for d in doses(clock)]

def open_medicines(request: gr.Request):
    return medicine_cards(request), None, ""


def refresh_cards(current, request: gr.Request):
    if current is None:
        return gr.skip()
    fresh = medicine_cards(request)
    return fresh if fresh != current else gr.skip()


def dose_identity(item):
    return (item["day"], item["id"], item["time"])


def review_early_dose(item, request: gr.Request):
    fresh = medicine_cards(request)
    match = next((m for m in fresh if dose_identity(m) == dose_identity(item)), None)
    if not match or match["status"] != "proxima":
        return None, "La agenda cambió. Revisa el estado actualizado de este horario.", fresh
    return dose_identity(match), f"Revisa el horario de las {match['time']} antes de guardar.", fresh


def confirm_reviewed_dose(item, pending, request: gr.Request):
    guard(request, {"adult"})
    if pending and tuple(pending) == dose_identity(item):
        msg = declare_dose(f"{item['id']} | {item['time']}", expected_day=item["day"], allow_early=True)
    else:
        msg = "Vuelve a elegir el horario que deseas revisar."
    return msg, medicine_cards(request), summary_html(), timeline_html(), None


def adult_home_update(request: gr.Request):
    guard(request, {"adult"})
    return summary_html()


def medicine_action(item,action,request:gr.Request):
    guard(request,{"adult"})
    if item["day"]!=str(now().date()):
        message="Cambió el día. Revisa el horario actualizado."
    else:
        choice=f"{item['id']} | {item['time']} | {item['name']}"
        if action=="confirm":
            message=declare_dose(choice, expected_day=item["day"])
        elif action=="seen":
            message=remember_seen(choice,request)
        elif action=="undo":
            with database() as c:
                cur=c.execute("""DELETE FROM confirmations WHERE medicine_id=? AND on_date=? AND at_time=?
                      AND declared_at=? AND medicine_id IN (SELECT id FROM medicines WHERE person_id=?)""",
                      (item["id"],item["day"],item["time"],item["declared_at"],PERSON_ID))
                if cur.rowcount:
                    c.execute("INSERT INTO events(person_id,kind,detail,created_at) VALUES(?,?,?,?)",
                              (PERSON_ID,"correccion",f"Se retiró la confirmación de {item['name']} a las {item['time']}",now().isoformat()))
            message=("Corrección guardada. El horario vuelve a estar sin confirmar." if cur.rowcount
                     else "El registro ya cambió. Revisa su estado actual.")
        else:
            message="Elige de nuevo la acción que deseas realizar."
    return message,medicine_cards(request),summary_html(),timeline_html()


def hear_instructions(section,request:gr.Request):
    guard(request,{"adult"})
    guide={"Mi día":"Puedes escuchar tu agenda. Para anotar cómo te fue, abre Registrar una actividad de hoy. Si hiciste algo distinto, elige Registrar una actividad extra.",
           "Hablar":"Toca Empezar a hablar. Cuando leas Te escucho, habla. Al terminar toca Terminé de hablar.",
           "Medicamentos":"Busca el nombre y la hora. Si el horario ya pasó, toca Ya lo tomé. Si es más tarde, toca Revisar este horario. Puedes volver sin guardar. Para deshacer una confirmación, toca Corregir registro.",
           "Cómo me siento":"Responde una pregunta a la vez. Puedes tocar una respuesta o dictarla. Al final toca Guardar.",
           "Actividades":"Guarda algo que disfrutes o busca lugares en tu zona.",
           "Cámara":"Puedes compartir la cámara con tu cuidador y detenerla cuando quieras.",
           "Ayuda":"Aquí puedes encontrar tus contactos de apoyo."}
    return speak(guide.get(section,guide["Mi día"])+" Para regresar al inicio, toca Volver a mi día.")


def parse_answer(words,topic):
    scale=(["muy mal","mal","regular","bien","muy bien"] if topic=="sleep" else
           ["muy baja","baja","media","alta","muy alta"])
    phrase=norm(words)
    for label in sorted(scale,key=len,reverse=True):
        if re.search(r"\b"+label+r"\b",phrase):
            return str(scale.index(label)+1)
    match=re.search(r"\b(uno|una|dos|tres|cuatro|cinco|[1-5])\b",phrase)
    if match:
        return {"uno":"1","una":"1","dos":"2","tres":"3","cuatro":"4","cinco":"5"}.get(match[1],match[1])
    return None


def dictate_answer(path,topic,request:gr.Request):
    guard(request,{"adult"})
    if not path:
        return gr.skip(),"Puedes elegir una respuesta o dictarla."
    words,status=transcribe(path)
    value=parse_answer(words,topic) if words else None
    if value:
        return value,f"Entendí «{words}». Revisa la opción marcada."
    return gr.skip(),status if not words else f"Entendí «{words}». Toca la opción que corresponda."


def build_app():
    init_db()
    has_demo = demo_end_date() is not None
    initial_voice = voice_preferences()
    with gr.Blocks(title="CENTINELA IA 2.1| DEMO", delete_cache=(3600, 3600)) as app:
        gr.HTML(banner())
        privacy_panel = gr.HTML(avisos.aviso_html(*initial_voice), js_on_load=avisos.LECTOR_JS, elem_id="privacidad-centinela")
        def sync_notice():
            saved = voice_preferences()
            return gr.skip() if saved == initial_voice else avisos.aviso_html(*saved)
        app.load(sync_notice, outputs=privacy_panel, show_progress="hidden", api_visibility="private")
        with gr.Column(elem_id="perfil-portada") as chooser:
            gr.HTML('<h2>Elige un perfil</h2><p>Explora el mismo caso ficticio desde dos puntos de vista.</p>')
            with gr.Row(elem_classes="perfil-fila"):
                with gr.Column(min_width=220,elem_classes="perfil-opcion"):
                    gr.HTML('<h3>Persona acompañada</h3><p>Consulta tu día, registra una actividad o habla con CENTINELA.</p>',
                            elem_classes="descripcion-perfil")
                    enter_person = gr.Button(lambda: f"Entrar como {person()['display_name'] or 'la persona'}",
                                             variant="primary",elem_id="entrar-persona")
                with gr.Column(min_width=220,elem_classes="perfil-opcion"):
                    gr.HTML('<h3>Cuidador</h3><p>Consulta las gráficas de evolución y revisa los registros del día.</p>',
                            elem_classes="descripcion-perfil")
                    enter_carer = gr.Button("Entrar como cuidador",variant="secondary",elem_id="entrar-cuidador")
        with gr.Column(visible=False,elem_id="adult-space") as adult_panel:
            with gr.Row(elem_classes="cent-session-bar"):
                gr.Markdown("**Perfil de la persona acompañada**")
                adult_switch=gr.Button("Cambiar de perfil", variant="secondary", size="sm", elem_classes="cent-logout", min_width=170)
            with gr.Row(elem_id="easy-tools"):
                back=gr.Button("🏠🌄🌔 Volver a mi día")
                font=gr.Button("A＋ Aumentar letra")
                guide=gr.Button("🔊 Escuchar instrucciones")
            section=gr.State("Mi día")
            instructions=gr.Audio(label="Instrucciones",visible=False,autoplay=True)
            guide_status=gr.Markdown()
            guide.click(lambda:gr.update(visible=True),outputs=instructions).then(hear_instructions,section,[instructions,guide_status])
            font.click(None,js="""()=>{const root=document.querySelector('#adult-space');const large=root.classList.toggle('large-type');
              const el=document.querySelector('#easy-tools button:nth-of-type(1)');const b=Array.from(document.querySelectorAll('#easy-tools button')).find(x=>x.textContent.includes('letra'));if(b){b.textContent=large?'A− Reducir letra':'A＋ Aumentar letra';b.setAttribute('aria-pressed',String(large));}}""")
            with gr.Accordion("Elegir la voz del asistente", open=False, elem_id="ajustes-voz") as voice_panel:
                voice_status_saved = gr.Markdown(current_voice_label(*initial_voice))
                voice_choice = gr.Radio([(v.etiqueta, k) for k, v in voces.VOCES.items()], value=initial_voice[0],
                                        label="¿Qué voz quieres escuchar?", elem_id="elegir-voz")
                pace_choice = gr.Radio([(v[0], k) for k, v in voces.RITMOS.items()], value=initial_voice[1],
                                       label="Ritmo de lectura", elem_id="ritmo-voz")
                gr.Markdown(f"Todas las voces dicen la misma frase. «{voces.FRASE_MUESTRA}»")
                with gr.Row():
                    sample_button = gr.Button("Escuchar muestra", variant="secondary")
                    choose_button = gr.Button("Usar esta voz", variant="primary")
                sample_player = gr.Audio(label="Muestra de voz", interactive=False, autoplay=True, visible=False,
                                         elem_id="muestra-de-voz")
                voice_control_outputs = [voice_choice, pace_choice, voice_status_saved, sample_player]
                voice_panel.expand(load_voice_controls, outputs=voice_control_outputs, api_visibility="private")
                for control in (voice_choice, pace_choice):
                    control.input(lambda: gr.update(value=None, visible=False), outputs=sample_player,
                                  queue=False, api_visibility="private")
                sample_button.click(preview_voice, [voice_choice, pace_choice], sample_player, api_visibility="private")
            with gr.Tabs() as adult_tabs:
                with gr.Tab("🏠🌄🌔 Mi día",id="home") as home_tab:
                    adult_home=gr.HTML("")
                    listen_btn=gr.Button("🔊 Escuchar mi día",variant="primary")
                    with gr.Row():
                        talk_shortcut=gr.Button("👨‍🦳🎤 Hablar con CENTINELA")
                        meds_shortcut=gr.Button("💊 Mis medicamentos")
                    talk_shortcut.click(lambda: gr.update(selected="hablar"),outputs=adult_tabs,queue=False)
                    meds_shortcut.click(lambda: gr.update(selected="meds"),outputs=adult_tabs,queue=False)
                    day_audio=gr.Audio(label="Mi día en voz alta",autoplay=True,visible=False)
                    day_status=gr.Textbox(label="Lectura de mi día",visible=False)
                    listen_btn.click(lambda: (gr.update(visible=True),gr.update(visible=True,value="Preparando la lectura…")),
                                     outputs=[day_audio,day_status],queue=False).then(listen_today,outputs=[day_audio,day_status])
                    with gr.Accordion("Registrar una actividad de hoy", open=False, elem_id="registro-rutinas") as day_log:
                        gr.HTML(avisos.nota("día"))
                        goal=gr.Dropdown(choices=[], label="¿Qué actividad de tu agenda quieres registrar?",
                                         info="Las actividades de hoy aparecen por hora.")
                        outcome=gr.Radio([("La hice", "Realizada"), ("La dejé para después", "Pospuesta"),
                                          ("Hoy no la haré", "Cancelada")], label="¿Cómo te fue?")
                        obstacle=gr.Textbox(label="Una nota, si quieres")
                        done=gr.Button("Guardar mi actividad", variant="primary")
                        day_feedback=gr.Textbox(label="Mi registro de actividad", interactive=False)
                        done.click(save_outcome,[goal,outcome,obstacle],day_feedback).then(adult_home_update,outputs=adult_home)
                        with gr.Accordion("Registrar una actividad extra",open=False):
                            extra_title=gr.Textbox(label="¿Qué más hiciste hoy?",placeholder="Por ejemplo, jugué dominó")
                            extra_note=gr.Textbox(label="Nota sobre esta actividad (opcional)")
                            extra_btn=gr.Button("Guardar actividad extra",variant="primary")
                            extra_feedback=gr.Textbox(label="Mi actividad extra",interactive=False)
                            extra_btn.click(save_extra_activity,[extra_title,extra_note],
                                            [extra_feedback,extra_title,extra_note]).then(adult_home_update,outputs=adult_home)
                    day_log.expand(load_today_goals,outputs=goal)
                    home_tab.select(load_today_goals,outputs=goal)
                    home_timeline=gr.HTML("")
                    adult_refresh=gr.Button("🔄 Actualizar mi día",variant="secondary")
                with gr.Tab("🫩😴😓🙂😀 Cómo me siento",id="evolucion") as evo_tab:
                    gr.HTML(avisos.nota("bienestar"))
                    with gr.Column() as sleep_step:
                        sleep=gr.Radio([(v,str(i)) for i,v in enumerate(["Muy mal","Mal","Regular","Bien","Muy bien"],1)],label="1 de 2 · ¿Cómo dormiste?")
                        with gr.Accordion("🎙️ Prefiero decirlo en voz alta",open=False):
                            gr.HTML(avisos.nota("dictado"))
                            sleep_audio=gr.Audio(sources=["microphone","upload"],type="filepath",label="Por ejemplo: dormí bien")
                            sleep_audio.change(dictate_answer,[sleep_audio,gr.State("sleep")],[sleep,sleep_notice:=gr.Markdown()])
                        forward=gr.Button("Continuar",variant="primary")
                    with gr.Column(visible=False) as energy_step:
                        energy=gr.Radio([(v,str(i)) for i,v in enumerate(["Muy baja","Baja","Media","Alta","Muy alta"],1)],label="2 de 2 · ¿Cómo está tu energía?")
                        with gr.Accordion("🎙️ Prefiero decirlo en voz alta",open=False):
                            gr.HTML(avisos.nota("dictado"))
                            en_audio=gr.Audio(sources=["microphone","upload"],type="filepath",label="Por ejemplo: mi energía está alta")
                            en_audio.change(dictate_answer,[en_audio,gr.State("energy")],[energy,en_notice:=gr.Markdown()])
                        daily_note=gr.Textbox(label="¿Quieres añadir algo? (opcional)")
                        with gr.Accordion("Dictar una nota opcional",open=False):
                            gr.HTML(avisos.nota("dictado"))
                            note_audio=gr.Audio(sources=["microphone","upload"],type="filepath",label="Mi nota de voz")
                            note_send=gr.Button("Pasar mi nota a texto")
                            note_feedback=gr.Markdown()
                            note_send.click(adult_transcribe,note_audio,[daily_note,note_feedback])
                        save_check=gr.Button("Guardar mis respuestas",variant="primary")
                        prev=gr.Button("Volver a la primera pregunta")
                    status=gr.Textbox(label="Mi registro",interactive=False)
                    forward.click(lambda:(gr.update(visible=False),gr.update(visible=True)),outputs=[sleep_step,energy_step])
                    prev.click(lambda:(gr.update(visible=True),gr.update(visible=False)),outputs=[sleep_step,energy_step])
                    save_check.click(save_checkin,[energy,sleep,daily_note],status)
                    with gr.Accordion("Mis metas y actividades",open=False):
                        jump_to_log=gr.Button("Registrar cómo me fue hoy")
                        jump_to_log.click(lambda:(gr.update(selected="home"),gr.update(open=True),"Mi día"),
                                          outputs=[adult_tabs,day_log,section],queue=False).then(load_today_goals,outputs=goal).then(
                            fn=None,js="() => document.querySelector('#registro-rutinas')?.scrollIntoView({block:'center'})")
                        title=gr.Textbox(label="¿Qué rutina quieres añadir a tu agenda?")
                        days=gr.CheckboxGroup(DAYS,label="Días de la semana")
                        hh=gr.Textbox(label="Hora opcional",placeholder="11:00")
                        create_goal=gr.Button("Guardar mi rutina")
                        goal_feedback=gr.Textbox(label="Mi nueva rutina",interactive=False)
                        create_goal.click(save_goal,[title,days,hh],[goal_feedback,goal]).then(adult_home_update,outputs=adult_home)
                    with gr.Accordion("Mis permisos y preferencias",open=False):
                        categories=gr.CheckboxGroup(
                            [("Bienestar", "Bienestar"), ("Actividades realizadas (metas)", "Metas"),
                             ("Confirmaciones de medicamentos (horarios)", "Horarios")],
                            label="¿Qué gráficas quieres compartir con tu cuidador?")
                        preview=gr.Markdown()
                        categories.change(sharing_preview,categories,preview,queue=False)
                        spoken=gr.Checkbox(label="Habilitar sugerencia hablada para revisar un horario")
                        pref_btn=gr.Button("Guardar preferencias")
                        pref_feedback=gr.Textbox(label="Mis preferencias",interactive=False)
                        pref_btn.click(save_prefs,[categories,spoken],pref_feedback)
                        hint_btn=gr.Button("Escuchar sugerencia de hoy")
                        hint_audio=gr.Audio(label="Sugerencia",autoplay=True)
                        hint_btn.click(read_hint,outputs=[hint_audio,status])
                    with gr.Accordion("Ver mi evolución",open=False):
                        own_period=gr.Radio([PERIOD_DEMO,PERIOD_RECENT],value=PERIOD_RECENT,
                                            label="¿Qué periodo quieres ver?",visible=has_demo)
                        report_btn=gr.Button("Actualizar mi evolución")
                        report=gr.HTML()
                        plot=gr.Plot(label="Energía y descanso declarados")
                        with gr.Accordion("Detalles del modelo de recordatorios",open=False):
                            gr.HTML(avisos.nota("evolución propia"))
                            score=gr.Textbox(label="Estimación de confirmaciones · experimental",interactive=False)
                        report_btn.click(evolution_view,own_period,[report,plot,score])
                        own_period.input(evolution_view,own_period,[report,plot,score])
                    evo_tab.select(load_personal,outputs=[goal,categories,spoken]).then(
                        sharing_preview,categories,preview).then(evolution_view,own_period,[report,plot,score])
                with gr.Tab("🎙️ Hablar",id="hablar") as talk_tab:
                    gr.HTML(avisos.nota("hablar"))
                    mic=gr.Button("🎙️ Empezar a hablar",variant="primary",elem_id="single-mic")
                    gr.HTML('<p id="mic-feedback" role="status">Toca el botón y espera a leer «Te escucho».</p>')
                    payload=gr.Textbox(visible=False)
                    mic.click(None,outputs=payload,js=RECORD_JS,queue=False)
                    previous_recording=gr.State(None)
                    chatbot=gr.Chatbot(label="Nuestra conversación",height=240)
                    with gr.Row():
                        ask_med=gr.Button("Consultar mis horarios de medicamentos")
                        ask_routines=gr.Button("Consultar mis actividades de hoy")
                    msg=gr.Textbox(label="Mi mensaje",placeholder="¿Qué actividades tengo hoy?")
                    send=gr.Button("Enviar mi mensaje")
                    with gr.Accordion("Servicios externos opcionales", open=False):
                        gr.Markdown("Puedes usar las funciones básicas con estas opciones apagadas. Si cambias de perfil, se apagan de nuevo.")
                        has_openai = bool(os.getenv("OPENAI_API_KEY", "").strip())
                        external_chat=gr.Checkbox(value=False, interactive=has_openai,
                            label="Permitir conversación con OpenAI",
                            info=("En consultas abiertas se enviarán tu mensaje y hasta ocho mensajes previos de este chat, incluidos los que ya escribiste."
                                  if has_openai else "La conversación externa está deshabilitada en esta presentación."))
                        google_voice=gr.Checkbox(value=False, label="Usar la voz de Google para este chat",
                            info="Si la activas, Google recibirá el texto de las respuestas para leerlas con su voz. Puedes desmarcarla o pulsar «Usar esta voz» para volver a la voz del perfil.")
                    with gr.Accordion("Usar un audio de ejemplo o un archivo",open=False):
                        audio=gr.Audio(sources=["microphone","upload"],type="filepath",label="Grabar o subir un archivo")
                        demo_audio=gr.Button("Probar una voz de ejemplo")
                        demo_audio.click(lambda: str(Path(__file__).with_name("voz_ejemplo.mp3")),outputs=audio,api_visibility="private")
                        process_voice=gr.Button("Volver a procesar el audio")
                        transcription=gr.Button("Copiar el último mensaje para corregirlo")
                    transcript_view=gr.Textbox(label="Esto entendió CENTINELA",interactive=False,lines=2)
                    transcript_status=gr.Markdown("Puedes preguntarme qué actividades tienes hoy.")
                    last_reply=gr.Textbox(label="Respuesta del asistente",interactive=False,lines=3)
                    reply_audio=gr.Audio(label="Escuchar respuesta de CENTINELA",autoplay=True,interactive=False)
                    voice_btn=gr.Button("🔊 Repetir respuesta en voz alta",variant="secondary")
                    voice_status=gr.Markdown()
                    # Procesar el valor que ya llegó al servidor, también al subir un archivo.
                    audio.start_recording(lambda: "Grabando. Habla y luego pulsa Detener.",outputs=transcript_status,queue=False)
                    voice_outputs=[chatbot,msg,last_reply,transcript_view,transcript_status,reply_audio,voice_status,previous_recording]
                    for trigger, fn, source in [(audio.change,handle_recording,audio),
                                                (process_voice.click,retry_recording,audio),
                                                (payload.change,record_from_browser,payload)]:
                        trigger(fn,[source,chatbot,previous_recording,external_chat,google_voice],voice_outputs,api_visibility="private",
                                show_progress="minimal",concurrency_id="voz",concurrency_limit=1)
                    transcription.click(lambda text: text or "",[transcript_view],msg,api_visibility="private")
                    send_event=send.click(adult_chat,[msg,chatbot,external_chat],[chatbot,msg,last_reply],api_visibility="private")
                    send_event.then(adult_speak,[last_reply,google_voice],[reply_audio,voice_status],api_visibility="private")
                    submit_event=msg.submit(adult_chat,[msg,chatbot,external_chat],[chatbot,msg,last_reply],api_visibility="private")
                    submit_event.then(adult_speak,[last_reply,google_voice],[reply_audio,voice_status],api_visibility="private")
                    voice_btn.click(adult_speak,[last_reply,google_voice],[reply_audio,voice_status],api_visibility="private")
                    for button, question in [(ask_med,"¿Qué tengo que tomar hoy?"),(ask_routines,"¿Qué actividades tengo hoy?")]:
                        button.click(adult_chat,[gr.State(question),chatbot,external_chat],[chatbot,msg,last_reply],
                                     api_visibility="private").then(adult_speak,[last_reply,google_voice],[reply_audio,voice_status],api_visibility="private")
                with gr.Tab("💊 Mis medicamentos",id="meds") as meds_tab:
                    gr.Markdown("### Medicamentos de hoy")
                    gr.HTML(avisos.nota("medicamentos"))
                    dose_select=gr.Dropdown(choices=[],visible=False)
                    dose_msg=gr.Textbox(label="Mi registro",interactive=False)
                    cards=gr.State(None)
                    pending_early=gr.State(None)
                    meds_tab.select(open_medicines,outputs=[cards,pending_early,dose_msg])
                    @gr.render(inputs=[cards,pending_early])
                    def render_medicines(items,pending):
                        if not items:
                            if items is not None:
                                gr.Markdown("Hoy no tienes horarios vigentes en tu agenda.")
                            return
                        for item in items:
                            row_key=f"{item['day']}-{item['id']}-{item['time']}"
                            with gr.Group(key=row_key,elem_id=f"horario-{item['id']}-{item['time'].replace(':','')}"):
                                gr.HTML(f"<div class='cent-card'><h3>{safe(item['name'])} · {friendly_time(item['time'])}</h3>"
                                        f"<p>{safe(item['instruction'])}</p>{status_tag(item['status'])}</div>")
                                current=gr.State(item)
                                if item["status"]=="proxima":
                                    if pending and tuple(pending)==dose_identity(item):
                                        gr.HTML(f"<div class='cent-review' role='status'><strong>Este horario es más tarde.</strong>"
                                                f"<p>¿Ya tomaste {safe(item['name'])} del horario de las {safe(item['time'])}?</p></div>")
                                        with gr.Row():
                                            cancel=gr.Button("Volver sin guardar")
                                            accept=gr.Button("Sí, ya lo tomé", variant="primary")
                                        cancel.click(lambda:(None,"De acuerdo. El horario sigue sin confirmar."),
                                                     outputs=[pending_early,dose_msg],api_visibility="private")
                                        accept.click(confirm_reviewed_dose,[current,pending_early],
                                                     [dose_msg,cards,adult_home,home_timeline,pending_early],api_visibility="private")
                                    else:
                                        review=gr.Button(f"Revisar este horario · {item['time']}")
                                        review.click(review_early_dose,current,[pending_early,dose_msg,cards],api_visibility="private")
                                    continue
                                confirmed=item["status"]=="confirmada"
                                action=gr.Button("Corregir registro" if confirmed else "Ya lo tomé",
                                                 variant="secondary" if confirmed else "primary")
                                action.click(medicine_action,[current,gr.State("undo" if confirmed else "confirm")],
                                             [dose_msg,cards,adult_home,home_timeline],api_visibility="private")
                                if item["status"]=="pendiente" and item["seen"]:
                                    gr.Markdown("Ya registraste que viste el aviso.")
                                elif item["status"]=="pendiente":
                                    seen=gr.Button("Solo vi el aviso")
                                    seen.click(medicine_action,[current,gr.State("seen")],[dose_msg,cards,adult_home,home_timeline])
                with gr.Tab("⛹️🤸🤾‍♀️ Actividades") as act_tab:
                    gr.Markdown("### Lo que te gusta hacer")
                    gr.HTML(avisos.nota("actividades"))
                    fav=gr.Textbox(label="Actividad favorita",placeholder="Ej.: pintura, lectura, baile")
                    freq=gr.Dropdown(["Diaria","Semanal","Fines de semana","Ocasional"],value="Semanal",label="¿Con qué frecuencia te gustaría hacerla?")
                    note=gr.Textbox(label="Preferencias de accesibilidad u observaciones",placeholder="Ej.: prefiero actividades sentadas")
                    fav_btn=gr.Button("💚 Guardar actividad",variant="primary")
                    act_msg=gr.Markdown()
                    suggestions=gr.Markdown("")
                    fav_btn.click(adult_add_activity,[fav,freq,note],[act_msg,suggestions,adult_home])
                    gr.Markdown("### Explorar lugares cercanos")
                    gr.HTML(avisos.nota("lugares"))
                    with gr.Row():
                        search_term=gr.Textbox(label="¿Qué quieres hacer?",placeholder="Taller de pintura")
                        zone=gr.Textbox(label="Zona general autorizada (no domicilio)",placeholder="Ej.: Coyoacán, CDMX")
                    search_btn=gr.Button("Buscar con Google Places" if os.getenv("GOOGLE_MAPS_API_KEY","").strip() else "Preparar búsqueda en Google Maps", variant="secondary")
                    search_results=gr.Markdown()
                    search_btn.click(adult_places,[search_term,zone],[search_results])
                with gr.Tab("📹 Mi cámara y privacidad") as cam_tab:
                    gr.HTML(avisos.nota("cámara"))
                    gr.Markdown("Si la señal se interrumpe durante 25 segundos, vuelve a tocar **Compartir cámara con mi cuidador** para reanudarla.")
                    with gr.Row():
                        adult_start_button=gr.Button("📹 Compartir cámara con mi cuidador",variant="primary")
                        adult_stop_button=gr.Button("🔒 Dejar de compartir",variant="stop")
                    adult_cam_notice=gr.Markdown("La cámara está apagada. Nadie puede ver imágenes de este dispositivo.")
                    adult_cam_input=gr.Image(label="Mi webcam (pulsa para iniciar el video)",sources=["webcam"],
                                             type="numpy",streaming=True,visible=False,buttons=[])
                    camera_timer=gr.Timer(value=3,active=False)
                    camera_controls=[adult_cam_input,adult_cam_notice,camera_timer]
                    adult_start_button.click(adult_camera_start,outputs=camera_controls,api_visibility="private")
                    adult_stop_button.click(adult_camera_stop,outputs=camera_controls,api_visibility="private")
                    camera_timer.tick(check_adult_camera,outputs=camera_controls,api_visibility="private",show_progress="hidden")
                    adult_cam_input.stream(adult_camera_frame,inputs=[adult_cam_input],outputs=[adult_cam_notice],
                                           stream_every=1.0,time_limit=90,concurrency_limit=1,
                                           show_progress="hidden",api_visibility="private")
                with gr.Tab("🆘 Ayuda") as help_tab:
                    gr.HTML(avisos.nota("ayuda"))
                    adult_support=gr.Markdown("")
            for tab,name in [(home_tab,"Mi día"),(evo_tab,"Cómo me siento"),(meds_tab,"Medicamentos"),(talk_tab,"Hablar"),(act_tab,"Actividades"),(cam_tab,"Cámara"),(help_tab,"Ayuda")]:
                tab.select(lambda value=name:value,outputs=section,queue=False)
            meds_shortcut.click(open_medicines,outputs=[cards,pending_early,dose_msg])
            meds_shortcut.click(lambda:"Medicamentos",outputs=section,queue=False)
            talk_shortcut.click(lambda:"Hablar",outputs=section,queue=False)
            back.click(lambda:gr.update(selected="home"),outputs=adult_tabs,queue=False).then(lambda:"Mi día",outputs=section)
            adult_refresh.click(refresh_adult,inputs=[dose_select],outputs=[adult_home,home_timeline,dose_select,suggestions,adult_support])
            adult_timer=gr.Timer(value=45,active=False)
            adult_timer.tick(refresh_adult,inputs=[dose_select],outputs=[adult_home,home_timeline,dose_select,suggestions,adult_support],show_progress="hidden")
            adult_timer.tick(refresh_cards,cards,cards,show_progress="hidden",api_visibility="private")
        with gr.Column(visible=False) as carer_panel:
            with gr.Row(elem_classes="cent-session-bar"):
                gr.Markdown("**Perfil del cuidador**")
                carer_switch=gr.Button("Cambiar de perfil", variant="secondary", size="sm", elem_classes="cent-logout", min_width=170)
            with gr.Tabs():
                with gr.Tab("Evolución compartida") as shared_tab:
                    gr.HTML(avisos.nota("compartida"))
                    periodos = ([PERIOD_DEMO] if has_demo else []) + [PERIOD_RECENT, evolucion.SEMANA, evolucion.HOY]
                    shared_period = gr.Radio(periodos, value=periodos[0], label="Periodo de las gráficas")
                    shared_activity = gr.Dropdown(choices=[(evolucion.ETIQUETA_TODAS,evolucion.TODAS)], value=evolucion.TODAS,
                        label="Actividad para ver en detalle", visible=False, elem_id="filtro-actividad")
                    shared_heading = gr.HTML(elem_id="resumen-evolucion")
                    shared_btn = gr.Button("Actualizar evolución compartida", variant="secondary")
                    shared_activities = gr.Plot(label="Actividades · resultados por rutina", format="png", visible=False,
                                               elem_classes="weekly-chart", elem_id="grafica-actividades")
                    shared_wellbeing = gr.Plot(label="Bienestar · energía y descanso declarados", format="png", visible=False,
                                               elem_classes="weekly-chart", elem_id="grafica-bienestar")
                    shared_medicines = gr.Plot(label="Medicamentos · confirmaciones por nombre y hora", format="png", visible=False,
                                               elem_classes="weekly-chart", elem_id="grafica-medicamentos")
                    with gr.Accordion("Cifras exactas y detalle por fecha", open=False):
                        shared_week = gr.Dropdown(choices=[], label="Semana del detalle diario", visible=False, elem_id="semana-detalle")
                        shared_detail = gr.HTML(elem_id="detalle-evolucion")
                        shared_score = gr.Textbox(label="Estimación experimental con el historial de horarios", interactive=False, visible=False)
                    shared_inputs = [shared_period, shared_activity, shared_week]
                    shared_outputs = [shared_heading, shared_wellbeing, shared_activities, shared_medicines,
                                      shared_detail, shared_score, shared_activity, shared_week]
                    shared_btn.click(caregiver_evolution, shared_inputs, shared_outputs, api_visibility="private")
                    shared_tab.select(caregiver_evolution, shared_inputs, shared_outputs, api_visibility="private")
                    for componente in shared_inputs:
                        componente.input(caregiver_evolution, shared_inputs, shared_outputs, api_visibility="private")
                with gr.Tab("📊 Resumen"):
                    gr.HTML(avisos.nota("resumen"))
                    carer_summary=gr.HTML("")
                    carer_timeline=gr.HTML("")
                    refresh_carer_btn=gr.Button("🔄 Actualizar seguimiento",variant="secondary")
                    carer_history=gr.Markdown("")
                with gr.Tab("💊 Plan de medicamentos"):
                    gr.Markdown("### Plan de medicamentos")
                    gr.HTML(avisos.nota("plan"))
                    med_name=gr.Textbox(label="Nombre del medicamento de prueba",placeholder="Medicamento A")
                    med_instruction=gr.Textbox(label="Indicación del profesional",placeholder="Ej.: indicación ya prescrita")
                    med_hours=gr.Textbox(label="Horarios DIARIOS en formato 24 h, separados por comas",placeholder="08:00, 20:00")
                    med_notes=gr.Textbox(label="Notas opcionales")
                    save_med=gr.Button("💊 Guardar horarios",variant="primary")
                    med_notice=gr.Markdown()
                    med_table=gr.Dataframe(value=pd.DataFrame(columns=MED_HEADERS),headers=MED_HEADERS,interactive=False,label="Medicamentos")
                    med_opt=gr.Dropdown(choices=[],label="Medicamento que deseas desactivar")
                    stop_med=gr.Button("Desactivar medicamento",variant="secondary")
                    save_med.click(carer_add_med,[med_name,med_instruction,med_hours,med_notes],[med_notice,med_table,med_opt,carer_timeline,carer_summary])
                    stop_med.click(carer_remove_med,[med_opt],[med_notice,med_table,med_opt,carer_timeline,carer_summary])
                with gr.Tab("⛹️🤸🤾‍♀️ Actividades"):
                    gr.Markdown("### Preferencias y actividades favoritas")
                    gr.HTML(avisos.nota("gustos"))
                    carer_fav=gr.Textbox(label="Actividad favorita",placeholder="Ej.: lectura")
                    carer_freq=gr.Dropdown(["Diaria","Semanal","Fines de semana","Ocasional"],value="Semanal",label="Frecuencia deseada")
                    carer_notes=gr.Textbox(label="Notas y accesibilidad")
                    carer_act_save=gr.Button("Guardar actividad",variant="primary")
                    carer_act_status=gr.Markdown()
                    carer_activity_table=gr.Dataframe(value=pd.DataFrame(columns=ACT_HEADERS),headers=ACT_HEADERS,interactive=False)
                    carer_act_save.click(carer_add_activity,[carer_fav,carer_freq,carer_notes],[carer_act_status,carer_activity_table])
                with gr.Tab("👪 Familia y perfil"):
                    gr.Markdown("### Personalización de la persona acompañada")
                    gr.HTML(avisos.nota("familia"))
                    name_field=gr.Textbox(label="Nombre de pila")
                    zone_field=gr.Textbox(label="Zona general de búsqueda, opcional")
                    save_profile=gr.Button("Guardar nombre y zona",variant="primary")
                    profile_status=gr.Markdown()
                    save_profile.click(carer_set_profile,[name_field,zone_field],[profile_status,carer_summary])
                    gr.Markdown("### Contactos autorizados (usar ficticios en esta demo)")
                    contact_name=gr.Textbox(label="Nombre del contacto")
                    contact_relation=gr.Textbox(label="Relación",placeholder="Familiar o cuidador")
                    contact_phone=gr.Textbox(label="Teléfono internacional, solo números")
                    save_contact=gr.Button("Guardar contacto",variant="primary")
                    contact_status=gr.Markdown()
                    contact_df=gr.Dataframe(value=pd.DataFrame(columns=CONTACT_HEADERS),headers=CONTACT_HEADERS,interactive=False)
                    hidden_support=gr.Markdown(visible=False)
                    save_contact.click(carer_add_contact,[contact_name,contact_relation,contact_phone],[contact_status,contact_df,hidden_support])
                with gr.Tab("📹 Cámara remota"):
                    gr.HTML(avisos.nota("remota"))
                    with gr.Row():
                        carer_watch=gr.Button("👁️ Ver cámara autorizada",variant="primary")
                        carer_leave=gr.Button("🔒 Dejar de ver",variant="secondary")
                    watching=gr.State(False)
                    carer_video=gr.HTML(video_placeholder("Vista cerrada","Pulsa Ver cámara para empezar."))
                    carer_video_status=gr.Markdown("La visualización está desactivada.")
                    video_timer=gr.Timer(value=2.0,active=False)
                    carer_watch.click(caregiver_open_video,outputs=[watching,carer_video,carer_video_status,video_timer],api_visibility="private")
                    carer_leave.click(caregiver_close_video,outputs=[watching,carer_video,carer_video_status,video_timer],api_visibility="private")
                    video_timer.tick(caregiver_poll_video,inputs=[watching],outputs=[carer_video,carer_video_status],
                                     show_progress="hidden",api_visibility="private",concurrency_limit=2)
            refresh_carer_btn.click(refresh_carer,outputs=[carer_summary,carer_timeline,med_table,med_opt,carer_activity_table,contact_df,carer_history])
            carer_timer=gr.Timer(value=60,active=False)
            carer_timer.tick(refresh_carer,outputs=[carer_summary,carer_timeline,med_table,med_opt,carer_activity_table,contact_df,carer_history],show_progress="hidden")
        choose_button.click(save_voice, [voice_choice, pace_choice],
                            [voice_status_saved, privacy_panel, sample_player, google_voice], api_visibility="private")
        entry_outputs = [chooser,adult_panel,carer_panel,adult_home,home_timeline,dose_select,
            suggestions,adult_support,carer_summary,carer_timeline,med_table,med_opt,
            carer_activity_table,contact_df,carer_history,name_field,zone_field,adult_timer,carer_timer]
        enter_person.click(enter_demo,gr.State("adult"),entry_outputs,api_visibility="private",show_progress="hidden")
        enter_carer.click(enter_demo,gr.State("carer"),entry_outputs,api_visibility="private",show_progress="hidden").success(
            load_shared_evolution,inputs=shared_inputs,outputs=shared_outputs,api_visibility="private")
        for button in (adult_switch,carer_switch):
            button.click(leave_demo,queue=False,api_visibility="private").success(
                fn=None,js=RETURN_TO_PROFILES_JS,queue=False,api_visibility="private")
        app.unload(leave_demo)
    return app


def launch(*, block=None):
    init_db()
    print("\nCENTINELA IA 2.1 · DEMO")
    print("Abre el enlace, elige un perfil y usa «Cambiar de perfil» para volver a la portada.\n")
    interface = build_app().queue(default_concurrency_limit=3)
    interface.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", "10000")),
        share=False,
        theme=gr.themes.Soft(primary_hue="emerald", secondary_hue="amber"),
        css=CSS,
        show_error=False,
        enable_monitoring=False,
        prevent_thread_lock=True
    )
    if os.getenv("CENTINELA_INTERNAL_REMINDERS", os.getenv("ACOMPANA_INTERNAL_REMINDERS", "1"))=="1":
        # En Colab, los recordatorios siguen activos cuando la celda devuelve el control.
        process_due()
        threading.Thread(target=reminder_loop,args=(interface,),daemon=True).start()
    if block is None:
        block = not bool(getattr(sys, "ps1", sys.flags.interactive))
    if block:
        try:
            interface.block_thread()
        finally:
            interface.close()
    return interface


if __name__=="__main__":
    launch()

