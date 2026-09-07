import unittest

from qgis.core import (
    QgsRuleBasedRenderer,
    QgsSymbol,
    QgsVectorLayer,
    QgsWkbTypes,
)

from lizmap_server.get_legend_graphic import Category, GetLegendGraphicFilter


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
        # One category per rule, in the renderer order
        self.assertEqual(4, len(result))
        self.assertEqual(
            ["rule-1", same_label, "rule-2", same_label],
            [category.label for category in result],
        )

        for symbol in result:
            self.assertGreaterEqual(len(symbol.ruleKey), 1)
            self.assertTrue(symbol.checked)
            self.assertGreaterEqual(len(symbol.parentRuleKey), 1)
            self.assertEqual(0, symbol.scaleMaxDenom)
            self.assertEqual(0, symbol.scaleMinDenom)
            self.assertEqual("TRUE", symbol.expression)
            self.assertIn(symbol.title, ("rule-1", "same-label", "rule-2"))

        # Same label, but neither the same rule key nor the same parent
        self.assertNotEqual(result[1].ruleKey, result[3].ruleKey)
        self.assertEqual(result[0].ruleKey, result[1].parentRuleKey)
        self.assertEqual(result[2].ruleKey, result[3].parentRuleKey)

    def test_match_duplicated_labels(self):
        """Test that duplicated labels are matched in the renderer order."""
        categories = [
            self._category("rule-1"),
            self._category("same-label"),
            self._category("rule-2"),
            self._category("same-label"),
        ]

        labels = [category.label for category in categories]
        self.assertEqual(categories, GetLegendGraphicFilter._match_categories(labels, categories))

    def test_match_filtered_symbols(self):
        """Test matching when QGIS Server filtered some legend nodes out."""
        categories = [
            self._category("rule-1"),
            self._category("same-label"),
            self._category("rule-2"),
            self._category("same-label"),
        ]

        # The first branch is not in the JSON legend
        self.assertEqual(
            [categories[2], categories[3]],
            GetLegendGraphicFilter._match_categories(["rule-2", "same-label"], categories),
        )

    def test_match_unknown_label(self):
        """Test matching a label which is not in the renderer."""
        categories = [self._category("rule-1")]
        self.assertEqual(
            [None, categories[0]],
            GetLegendGraphicFilter._match_categories(["unknown", "rule-1"], categories),
        )

    def test_match_reordered_labels(self):
        """Test matching when the legend nodes have been reordered in the project."""
        categories = [self._category("rule-1"), self._category("rule-2")]

        # "rule-1" is behind the cursor, the fallback still finds it
        self.assertEqual(
            [categories[1], categories[0]],
            GetLegendGraphicFilter._match_categories(["rule-2", "rule-1"], categories),
        )

    @staticmethod
    def _category(label: str) -> Category:
        """A category, only the label matters for the matching."""
        return Category(
            label=label,
            ruleKey=f"{{{label}}}",
            checked=True,
            parentRuleKey="",
            scaleMaxDenom=0,
            scaleMinDenom=0,
            expression="TRUE",
            title=label,
        )
