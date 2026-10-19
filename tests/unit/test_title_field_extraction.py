"""tests/unit/test_title_field_extraction.py

Textos ficticios: no contienen datos de documentos reales.
"""

from dataclasses import asdict

import pytest

from src.application.title_field_extraction import extract_title_fields


@pytest.mark.parametrize("transform", [str.upper, str.lower, lambda text: text])
def test_extract_all_fields_regardless_of_case(transform):
    proposal = extract_title_fields("documento", transform(
        "Chasis: XYZ123456789\nModelo: Ruta 1.6\nDominio: AB123CD\n"
        "Año: 2020\nMarca: Ejemplo\nMotor: MOT987654"
    ))
    assert asdict(proposal) == {
        "id_documento": "documento", "patente": "AB123CD",
        "marca": transform("Ejemplo"), "modelo": transform("Ruta 1.6"),
        "numero_motor": "MOT987654", "numero_chasis": "XYZ123456789",
        "anio": 2020, "requiere_revision": True,
    }


def test_spaces_newlines_and_label_variants():
    proposal = extract_title_fields("doc", (
        "  Patente \t:\n  ABC 123\nMarca\n  Fabrica   Ejemplo\n"
        "Modelo: Ruta 2   Número de motor: M123\n"
        "N° de chasis: C456\nAño de fabricación: 2018\n"
    ))
    assert proposal.patente == "ABC123"
    assert proposal.marca == "Fabrica Ejemplo"
    assert proposal.modelo == "Ruta 2"
    assert proposal.numero_motor == "M123"
    assert proposal.numero_chasis == "C456"
    assert proposal.anio == 2018


@pytest.mark.parametrize("text", ["", "Título automotor\nTitular: Persona ficticia", "Marca:\nModelo:"])
def test_missing_fields(text):
    proposal = asdict(extract_title_fields("doc", text))
    assert all(proposal[field] is None for field in (
        "patente", "marca", "modelo", "numero_motor", "numero_chasis", "anio",
    ))
    assert proposal["requiere_revision"] is True


@pytest.mark.parametrize("text,field", [
    ("Dominio: desconocido", "patente"),
    ("Año: 2020 o 2021", "anio"),
    ("Motor: SIN DATOS", "numero_motor"),
    ("Chasis: ???", "numero_chasis"),
    ("Marca: Una\nMarca: Otra", "marca"),
    ("Dominio: AB123CD\nPatente: AC456EF", "patente"),
])
def test_unclear_or_conflicting_fields_are_null(text, field):
    assert getattr(extract_title_fields("doc", text), field) is None


def test_sanitized_title_with_coded_names_and_explicit_year():
    proposal = extract_title_fields("ficticio", (
        "número de dominio XY456ZA\nMARCA: 271-FABRICA FICTICIA\n"
        "MODELO: 823-SENDA 1.8\nNro.Motor: fict98765\n"
        "CHASIS/CUADRO: cuadro76543\nModelo Año: 2017\n"
        "Fecha de inscripción: 03/04/2018\nFecha de emisión: 05/06/2019"
    ))
    assert asdict(proposal) == {
        "id_documento": "ficticio", "patente": "XY456ZA", "marca": "FABRICA FICTICIA",
        "modelo": "SENDA 1.8", "numero_motor": "FICT98765",
        "numero_chasis": "CUADRO76543", "anio": 2017, "requiere_revision": True,
    }


@pytest.mark.parametrize("label", ["Nro.Motor", "Nro. Motor", "MOTOR Nº", "motor n°", "nRo.  mOtOr"])
def test_motor_labels(label):
    assert extract_title_fields("doc", f"{label}: fic12345").numero_motor == "FIC12345"


@pytest.mark.parametrize("label", ["Nro. Chasis", "Nro.Chasis", "CHASIS/CUADRO", "chasis / cuadro"])
def test_chassis_labels(label):
    assert extract_title_fields("doc", f"{label}: fic67890").numero_chasis == "FIC67890"


@pytest.mark.parametrize("label", ["DOMINIO:", "número de dominio", "NÚMERO  DE  DOMINIO", "numero de dominio"])
def test_domain_labels(label):
    assert extract_title_fields("doc", f"{label} XY456ZA").patente == "XY456ZA"


@pytest.mark.parametrize("label", ["Modelo Año", "modelo   año", "MODELO\nAÑO", "Modelo Anio"])
def test_model_year_is_not_model_name(label):
    proposal = extract_title_fields("doc", f"Modelo: Senda\n{label}:\n2017")
    assert proposal.modelo == "Senda"
    assert proposal.anio == 2017


@pytest.mark.parametrize("date_label", [
    "Fecha de inscripción", "Fecha de adquisición", "Fecha de emisión",
    "Fecha de nacimiento", "Fecha de vencimiento",
])
def test_other_dates_do_not_supply_year(date_label):
    assert extract_title_fields("doc", f"{date_label}: 2019").anio is None
    proposal = extract_title_fields("doc", f"{date_label}: 2019\nModelo Año: 2017")
    assert proposal.anio == 2017


@pytest.mark.parametrize("field,text,expected", [
    ("marca", "Marca: 271-Fabrica Ficticia\nMARCA: fabrica   ficticia", "Fabrica Ficticia"),
    ("modelo", "Modelo: 823-Senda 1.8\nMODELO: senda 1.8", "Senda 1.8"),
    ("numero_motor", "Nro.Motor: fic12345\nMOTOR Nº: FIC12345", "FIC12345"),
    ("numero_chasis", "Nro. Chasis: fic67890\nCHASIS/CUADRO: FIC67890", "FIC67890"),
    ("patente", "número de dominio xy456za\nDOMINIO: XY 456 ZA", "XY456ZA"),
    ("anio", "Modelo Año: 2017\nAño modelo: 2017", 2017),
    ("numero_motor", "Motor: SIN DATOS\nNro.Motor: fic12345", "FIC12345"),
])
def test_repeated_candidates_are_normalized_before_comparison(field, text, expected):
    assert getattr(extract_title_fields("doc", text), field) == expected


@pytest.mark.parametrize("field,text", [
    ("marca", "Marca: 271-Fabrica Una\nMarca: 321-Fabrica Dos"),
    ("modelo", "Modelo: 823-Senda\nModelo: 824-Ruta"),
    ("numero_motor", "Nro.Motor: fic111\nMOTOR Nº: fic222"),
    ("numero_chasis", "Nro.Chasis: fic333\nCHASIS/CUADRO: fic444"),
    ("patente", "número de dominio XY456ZA\nDOMINIO: XZ789AB"),
    ("anio", "Modelo Año: 2017\nModelo Año: 2018"),
])
def test_different_valid_candidates_are_not_chosen_arbitrarily(field, text):
    assert getattr(extract_title_fields("doc", text), field) is None


@pytest.mark.parametrize("field,label", [("marca", "Marca"), ("modelo", "Modelo")])
@pytest.mark.parametrize("value", ["FIC-271", "271 FICTICIO", "FICTICIO-1.8"])
def test_names_without_numeric_prefix_are_preserved(field, label, value):
    assert getattr(extract_title_fields("doc", f"{label}: {value}"), field) == value


def test_whitespace_and_case_in_extended_labels():
    proposal = extract_title_fields("doc", (
        "nÚmErO \t de\n dominio :\n xy456za\n"
        "Marca: 271 - Fabrica   Ficticia\nModelo: 823- Senda 1.8\n"
        "nRo. \n Motor : fic12345\nNro.\tChasis: fic67890\n"
        "mOdElO \n aÑo :\n2017"
    ))
    assert proposal.patente == "XY456ZA"
    assert proposal.marca == "Fabrica Ficticia"
    assert proposal.modelo == "Senda 1.8"
    assert proposal.numero_motor == "FIC12345"
    assert proposal.numero_chasis == "FIC67890"
    assert proposal.anio == 2017


@pytest.mark.parametrize("transform", [str.upper, str.lower, lambda text: text])
def test_real_layout_with_sanitized_values(transform):
    text = transform(
        "Mca. Chasis: FICTICIA Nro. Chasis: FIC123456789\n"
        "Fabricación Año: Modelo Año: 2016 Fecha de Adquisición: ---\n"
        "Fecha de inscripción: 01/02/2017\n"
        "CHASIS/CUADRO: FIC123456789 \n"
    )
    proposal = extract_title_fields("ficticio", text)
    assert proposal.numero_chasis == "FIC123456789"
    assert proposal.anio == 2016
    assert proposal.requiere_revision is True


@pytest.mark.parametrize("fabrication", ["", "2015"])
def test_model_year_is_separate_from_fabrication_and_other_dates(fabrication):
    proposal = extract_title_fields("doc", (
        f"Fabricación Año: {fabrication} Modelo Año: 2016 "
        "Fecha de Adquisición: 01/02/2018 Fecha de emisión: 03/04/2019\n"
    ))
    assert proposal.anio == 2016


def test_auxiliary_labels_are_not_vehicle_identifiers_or_model_year():
    proposal = extract_title_fields("doc", (
        "Mca. Chasis: FICTICIA Fabricación Año: 2015 "
        "Fecha de Adquisición: 01/02/2018"
    ))
    assert proposal.numero_chasis is None
    assert proposal.anio is None


def test_auxiliary_labels_preserve_real_chassis_and_year_conflicts():
    proposal = extract_title_fields("doc", (
        "Mca. Chasis: FICTICIA Nro. Chasis: FIC123456789\n"
        "CHASIS/CUADRO: FIC987654321\n"
        "Fabricación Año: Modelo Año: 2016 Fecha de Adquisición: ---\n"
        "Modelo Año: 2017 Fecha de emisión: 01/02/2018"
    ))
    assert proposal.numero_chasis is None
    assert proposal.anio is None
