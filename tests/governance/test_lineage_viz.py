from governance.lineage_viz import build_lineage_figure


def test_lineage_figure_projects_nodes_edges_and_hover_properties():
    lineage = {
        "nodes": [
            {
                "id": "EXC-1",
                "type": "Exception",
                "label": "Exception",
                "properties": {"fraud_label": "Unknown"},
            },
            {
                "id": "AUTH-1",
                "type": "AuthorizationDecision",
                "label": "ALLOW",
                "properties": {"reason_codes": ["LOW_RISK"]},
            },
        ],
        "edges": [{"source": "AUTH-1", "target": "EXC-1", "type": "DECIDES"}],
    }

    figure = build_lineage_figure(lineage)

    assert len(figure.data) == 3
    assert len(figure.data[2].x) == 2
    assert "fraud label: Unknown" in " ".join(figure.data[2].hovertext)
    assert list(figure.data[1].text) == ["DECIDES"]
    assert figure.layout.dragmode == "pan"
