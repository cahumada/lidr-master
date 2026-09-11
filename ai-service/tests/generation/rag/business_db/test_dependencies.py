"""The two hops, and the collision the first one has to survive.

|| Los dos saltos, y la colisión que el primero tiene que sobrevivir.
"""

from __future__ import annotations

from app.generation.rag.business_db.dependencies import (
    build_edges,
    fan_in_by_table,
    routines_for_codes,
)


class TestLongestMatchWins:
    """184 codes are substrings of another; the longest one takes the routine.

    || 184 códigos son substring de otro; el más largo se lleva la rutina.
    """

    def test_variant_keeps_its_own_routine(self) -> None:
        assigned = routines_for_codes(
            ["CA013", "CA013A"], ["INSPOSTCA013A", "INSPOSTCA013"]
        )
        assert assigned["CA013A"] == ["INSPOSTCA013A"]
        assert assigned["CA013"] == ["INSPOSTCA013"]

    def test_short_code_does_not_inherit(self) -> None:
        assigned = routines_for_codes(["CA013", "CA013A"], ["INSPOSTCA013A"])
        assert assigned["CA013"] == []

    def test_key_request_and_module_prefix(self) -> None:
        assigned = routines_for_codes(
            ["AG001", "AG001_K", "MAG001"],
            ["REAAG001_K", "REAMAG001", "INSAG001"],
        )
        assert assigned["AG001_K"] == ["REAAG001_K"]
        assert assigned["MAG001"] == ["REAMAG001"]
        assert assigned["AG001"] == ["INSAG001"]


class TestBoundaryGuard:
    """A verb prefix can glue a longer, spurious code onto the real one.

    || Un prefijo verbal puede pegar un código espurio más largo al real.
    """

    def test_the_prefix_does_not_manufacture_a_longer_code(self) -> None:
        # "INSCA001PKG" contains "SCA001" because the S of INS runs into CA001.
        # Longest-match alone handed SCA001 all 30 routines of CA001.
        # || La S de INS se junta con CA001 y fabrica SCA001.
        assigned = routines_for_codes(["CA001", "SCA001"], ["INSCA001PKG"])
        assert assigned["CA001"] == ["INSCA001PKG"]
        assert assigned["SCA001"] == []

    def test_a_real_longer_code_still_wins(self) -> None:
        assigned = routines_for_codes(["CA001", "CA001M"], ["INSCA001MPKG"])
        assert assigned["CA001M"] == ["INSCA001MPKG"]
        assert assigned["CA001"] == []

    def test_a_separator_before_the_code_is_well_placed(self) -> None:
        assigned = routines_for_codes(["CA025"], ["INSROLES_CA025"])
        assert assigned["CA025"] == ["INSROLES_CA025"]

    def test_an_unconventional_name_anchors_nowhere(self) -> None:
        # No fallback: not anchoring is a fact, anchoring wrong is a lie.
        # || Sin fallback: no anclar es un hecho, anclar mal es una mentira.
        assigned = routines_for_codes(["BC003_K"], ["UPDCLIENTBC003_K"])
        assert assigned["BC003_K"] == []

    def test_length_four_never_anchors(self) -> None:
        # LOGO -> INSCOPYCATALOGO and MENU -> REAWINDOWSMENUPKG, domain §5.3.
        assigned = routines_for_codes(
            ["LOGO", "MENU"], ["INSCOPYCATALOGO", "REAWINDOWSMENUPKG"]
        )
        assert assigned == {}

    def test_matching_is_case_insensitive(self) -> None:
        assigned = routines_for_codes(["ca014"], ["INSPOSTCA014"])
        assert assigned["CA014"] == ["INSPOSTCA014"]


class TestFanIn:
    def test_counts_distinct_routines(self) -> None:
        fan = fan_in_by_table(
            [("R1", "COVER"), ("R2", "COVER"), ("R1", "COVER"), ("R1", "POLICY")]
        )
        assert fan == {"COVER": 2, "POLICY": 1}


class TestBuildEdges:
    def _built(self, descriptions: dict[str, str | None] | None = None):
        return build_edges(
            code_routines={"CA014": ["INSPOSTCA014", "INSVALCA014DB02", "REACA014"]},
            routine_tables={
                "INSPOSTCA014": ["COVER", "POLICY_HIS"],
                "INSVALCA014DB02": ["COVER", "NOPAYROLL"],
                "REACA014": ["COVER"],
            },
            descriptions=descriptions or {},
            fan_in={"COVER": 1037, "NOPAYROLL": 44, "POLICY_HIS": 440},
        )

    def test_orders_by_coverage(self) -> None:
        edges = self._built()["CA014"]
        assert edges[0].table_name == "COVER"
        assert edges[0].routine_hits == 3
        assert edges[0].routine_total == 3
        assert edges[0].coverage == 1.0

    def test_provenance_travels(self) -> None:
        edges = self._built()["CA014"]
        assert edges[0].via_routines == ["INSPOSTCA014", "INSVALCA014DB02", "REACA014"]
        assert edges[0].origin == "dependency_graph"

    def test_validation_only_table(self) -> None:
        edges = {edge.table_name: edge for edge in self._built()["CA014"]}
        assert edges["NOPAYROLL"].role == "validation"

    def test_history_suffix(self) -> None:
        edges = {edge.table_name: edge for edge in self._built()["CA014"]}
        assert edges["POLICY_HIS"].role == "historical"

    def test_fan_in_travels_but_does_not_demote(self) -> None:
        # COVER has the highest fan-in of the three and is still not demoted:
        # measured, the annotated tables are the high-fan-in ones.
        # || COVER tiene el fan-in más alto y no se degrada.
        edges = {edge.table_name: edge for edge in self._built()["CA014"]}
        assert edges["COVER"].fan_in == 1037
        assert edges["COVER"].role == "unknown"

    def test_table_without_dictionary_still_produces_an_edge(self) -> None:
        edges = {edge.table_name: edge for edge in self._built()["CA014"]}
        assert "COVER" in edges

    def test_code_without_routines(self) -> None:
        built = build_edges(
            code_routines={"CA999": []},
            routine_tables={},
            descriptions={},
            fan_in={},
        )
        assert built["CA999"] == []

    def test_routine_without_tables(self) -> None:
        built = build_edges(
            code_routines={"CA999": ["INSCA999"]},
            routine_tables={"INSCA999": []},
            descriptions={},
            fan_in={},
        )
        assert built["CA999"] == []
