import unittest

from qgis.core import (
    Qgis,
    QgsRuleBasedRenderer,
    QgsSymbol,
    QgsVectorLayer,
    QgsWkbTypes,
)

from lizmap_server.get_legend_graphic import GetLegendGraphicFilter


class TestLegend(unittest.TestCase):
    def test_regexp_feature_count(self):
        """Test the regexp about the feature count."""
        result = GetLegendGraphicFilter.match_label_feature_count("A label [22]")
        self.assertEqual(result.group(1), "A label")

        result = GetLegendGraphicFilter.match_label_feature_count("A label [≈2]")
        self.assertEqual(result.group(1), "A label")

        result = GetLegendGraphicFilter.match_label_feature_count("A label")
        self.assertIsNone(result)

    def test_duplicated_labels(self):
        """Test the legend with multiple sub-rules in the rule based rendered."""
        # noinspection PyTypeChecker
        root_rule = QgsRuleBasedRenderer.Rule(None)

        same_label = "same-label"

        # Rule 1 with symbol
        # noinspection PyUnresolvedReferences
        rule_1 = QgsRuleBasedRenderer.Rule(
            QgsSymbol.defaultSymbol(QgsWkbTypes.GeometryType.PointGeometry),
            label="rule-1",
        )
        root_rule.appendChild(rule_1)

        # Sub-rule to rule 1
        # noinspection PyTypeChecker
        rule_1_1 = QgsRuleBasedRenderer.Rule(None, label=same_label)
        rule_1.appendChild(rule_1_1)

        # Rule 2 with symbol
        # noinspection PyUnresolvedReferences
        rule_2 = QgsRuleBasedRenderer.Rule(
            QgsSymbol.defaultSymbol(QgsWkbTypes.GeometryType.PointGeometry),
            label="rule-2",
        )
        root_rule.appendChild(rule_2)

        # Sub-rule to rule 2
        # noinspection PyTypeChecker
        rule_2_1 = QgsRuleBasedRenderer.Rule(None, label=same_label)
        rule_2.appendChild(rule_2_1)

        layer = QgsVectorLayer("Point?field=fldtxt:string", "layer1", "memory")
        layer.setRenderer(QgsRuleBasedRenderer(root_rule))

        result = GetLegendGraphicFilter._extract_categories(layer)
        # TODO, this should be 4, as we have 4 rules
        self.assertEqual(3, len(list(result.keys())))

        for symbol in result.values():
            self.assertGreaterEqual(len(symbol.ruleKey), 1)
            self.assertTrue(symbol.checked)
            self.assertGreaterEqual(len(symbol.parentRuleKey), 1)
            self.assertEqual(0, symbol.scaleMaxDenom)
            self.assertEqual(0, symbol.scaleMinDenom)
            if Qgis.QGIS_VERSION_INT >= 32800:
                # I'm not sure since when, just looking at CI results
                self.assertEqual("TRUE", symbol.expression)
            else:
                self.assertEqual("", symbol.expression)
            self.assertIn(symbol.title, ("rule-1", "same-label", "rule-2"))
