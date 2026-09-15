import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root

    // themeBridge (ThemeBridge) y vm (SettingsViewModel) llegan por contexto.
    readonly property var colors: themeBridge.colors
    readonly property string iconFont: "Material Symbols Rounded"
    readonly property color accentColor: root.colors["accent"]

    function accentWithAlpha(a) {
        return Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, a)
    }

    Rectangle {
        anchors.fill: parent
        color: root.colors["bg_base"]
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ── Sidebar de categorías ─────────────────────────────────────
        Rectangle {
            Layout.preferredWidth: 210
            Layout.fillHeight: true
            color: "transparent"

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacingSm
                anchors.rightMargin: Theme.spacingSm
                anchors.topMargin: Theme.spacingMd
                spacing: Theme.spacingXxs

                Label {
                    text: "Ajustes"
                    color: root.colors["text_primary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeHeading
                    font.weight: Font.Bold
                    Layout.bottomMargin: Theme.spacingSm
                    Layout.leftMargin: Theme.spacingSm
                }

                Repeater {
                    model: vm.categories

                    delegate: Rectangle {
                        id: catBtn
                        required property int index
                        required property var modelData
                        readonly property bool active: vm.categoryIndex === index

                        Layout.fillWidth: true
                        Layout.preferredHeight: 40
                        radius: Theme.radiusMd
                        color: active ? root.accentWithAlpha(0.15)
                                      : (catMa.containsMouse ? root.accentWithAlpha(0.09) : "transparent")

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacingSm
                            spacing: Theme.spacingSm

                            Text {
                                text: catBtn.modelData.icon
                                font.family: root.iconFont
                                font.pixelSize: 18
                                color: catBtn.active ? root.accentColor : root.colors["text_secondary"]
                            }
                            Label {
                                text: catBtn.modelData.label
                                color: catBtn.active ? root.accentColor : root.colors["text_secondary"]
                                font.family: Theme.fontFamily
                                font.pixelSize: 13
                                font.weight: catBtn.active ? Font.Bold : Font.Medium
                                Layout.fillWidth: true
                            }
                        }
                        MouseArea {
                            id: catMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: vm.set_category(catBtn.index)
                        }
                    }
                }

                Item { Layout.fillHeight: true }
            }
        }

        // ── Página ────────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "transparent"

            Flickable {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacingXl
                anchors.rightMargin: Theme.spacingXl
                anchors.topMargin: Theme.spacingLg
                anchors.bottomMargin: 112
                contentWidth: width
                contentHeight: pageCol.height
                clip: true
                flickableDirection: Flickable.VerticalFlick

                ColumnLayout {
                    id: pageCol
                    width: parent ? parent.width : 600
                    spacing: Theme.spacingXs

                    Label {
                        text: vm.currentTitle
                        color: root.colors["text_primary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeHeading
                        font.weight: Font.Bold
                        Layout.bottomMargin: Theme.spacingSm
                    }

                    Repeater {
                        model: vm.rows

                        delegate: ColumnLayout {
                            id: rowDelegate
                            required property string rowType
                            required property string rowId
                            required property string label
                            required property string desc
                            required property var value
                            required property var options
                            required property double minV
                            required property double maxV
                            required property double stepV
                            required property string unitV
                            required property bool rowEnabled
                            required property string variant
                            required property bool password
                            required property int decimals
                            required property var items

                            Layout.fillWidth: true
                            spacing: 0

                            // ── Sección ───────────────────────────────
                            Label {
                                visible: rowDelegate.rowType === "section"
                                text: rowDelegate.label
                                color: root.accentColor
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.typeLabel
                                font.weight: Font.Bold
                                font.letterSpacing: 0.5
                                Layout.topMargin: Theme.spacingSm
                                Layout.bottomMargin: Theme.spacingXxs
                            }

                            // ── Fila estándar ──────────────────────────
                            Rectangle {
                                visible: rowDelegate.rowType !== "section"
                                         && rowDelegate.rowType !== "eq_bands"
                                Layout.fillWidth: true
                                Layout.preferredHeight: 64
                                radius: Theme.radiusMd
                                color: root.colors["bg_surface"]
                                border.width: 1
                                border.color: root.colors["border"]

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: Theme.spacingMd
                                    anchors.rightMargin: Theme.spacingMd
                                    spacing: Theme.spacingMd

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2

                                        Label {
                                            text: rowDelegate.label
                                            color: root.colors["text_primary"]
                                            font.family: Theme.fontFamily
                                            font.pixelSize: Theme.typeBody
                                            font.weight: Font.Medium
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                        Label {
                                            visible: rowDelegate.desc !== ""
                                            text: rowDelegate.desc
                                            color: root.colors["text_secondary"]
                                            font.family: Theme.fontFamily
                                            font.pixelSize: Theme.typeCaption
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                    }

                                    // toggle
                                    Rectangle {
                                        visible: rowDelegate.rowType === "toggle"
                                        width: 44; height: 26; radius: 13
                                        color: rowDelegate.value ? root.accentColor : root.colors["bg_high"]

                                        Rectangle {
                                            width: 20; height: 20; radius: 10
                                            color: "#FFFFFF"
                                            x: rowDelegate.value ? parent.width - 23 : 3
                                            anchors.verticalCenter: parent.verticalCenter
                                            Behavior on x { NumberAnimation { duration: 140 } }
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: vm.set_value(rowDelegate.rowId, !rowDelegate.value)
                                        }
                                    }

                                    // combo
                                    ComboBox {
                                        id: rowCombo
                                        visible: rowDelegate.rowType === "combo"
                                        model: rowDelegate.options
                                        textRole: "text"
                                        valueRole: "value"

                                        Component.onCompleted: {
                                            var idx = findIndexOfValue(rowDelegate.value)
                                            if (idx >= 0) currentIndex = idx
                                        }
                                        function findIndexOfValue(v) {
                                            for (var i = 0; i < count; i++)
                                                if (String(model[i].value) === String(v)) return i
                                            return -1
                                        }

                                        onActivated: vm.set_value(rowDelegate.rowId, currentValue)

                                        contentItem: Label {
                                            leftPadding: Theme.spacingSm
                                            text: rowCombo.displayText
                                            color: root.colors["text_primary"]
                                            font.family: Theme.fontFamily
                                            font.pixelSize: 13
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                        background: Rectangle {
                                            implicitWidth: 170
                                            implicitHeight: 34
                                            radius: Theme.radiusSm
                                            color: root.colors["bg_elevated"]
                                            border.width: 1
                                            border.color: root.colors["border"]
                                        }
                                        delegate: ItemDelegate {
                                            id: optDelegate
                                            required property var modelData
                                            width: rowCombo.width
                                            contentItem: Label {
                                                text: optDelegate.modelData.text
                                                color: root.colors["text_primary"]
                                                font.family: Theme.fontFamily
                                                font.pixelSize: 13
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                            background: Rectangle {
                                                color: optDelegate.hovered ? root.colors["bg_high"] : "transparent"
                                            }
                                        }
                                        popup: Popup {
                                            y: rowCombo.height
                                            width: rowCombo.width
                                            implicitHeight: contentItem.implicitHeight
                                            padding: Theme.spacingXxs
                                            contentItem: ListView {
                                                clip: true
                                                implicitHeight: contentHeight
                                                model: rowCombo.popup.visible ? rowCombo.delegateModel : null
                                                ScrollIndicator.vertical: ScrollIndicator {}
                                            }
                                            background: Rectangle {
                                                radius: Theme.radiusSm
                                                color: root.colors["bg_elevated"]
                                                border.width: 1
                                                border.color: root.colors["border"]
                                            }
                                        }
                                    }

                                    // slider (valor + unidad)
                                    RowLayout {
                                        visible: rowDelegate.rowType === "slider"
                                                     || rowDelegate.rowType === "preamp"
                                        spacing: Theme.spacingSm

                                        Slider {
                                            id: sld
                                            Layout.preferredWidth: 180
                                            from: rowDelegate.minV
                                            to: rowDelegate.maxV
                                            stepSize: 1
                                            value: (typeof rowDelegate.value === "number") ? rowDelegate.value : 0
                                            enabled: rowDelegate.rowEnabled
                                            onMoved: vm.set_value(rowDelegate.rowId, Math.round(value))

                                            background: Rectangle {
                                                x: sld.leftPadding
                                                y: sld.topPadding + sld.availableHeight / 2 - 2
                                                width: sld.availableWidth
                                                height: 4
                                                radius: 2
                                                color: root.colors["bg_high"]

                                                Rectangle {
                                                    width: sld.position * parent.width
                                                    height: 4
                                                    radius: 2
                                                    color: rowDelegate.rowEnabled ? root.accentColor : root.colors["text_secondary"]
                                                }
                                            }
                                            handle: Rectangle {
                                                x: sld.leftPadding + sld.visualPosition * (sld.availableWidth - width)
                                                y: sld.topPadding + sld.availableHeight / 2 - height / 2
                                                width: 16; height: 16; radius: 8
                                                color: rowDelegate.rowEnabled ? root.accentColor : root.colors["text_secondary"]
                                            }
                                        }

                                        Label {
                                            text: rowDelegate.rowType === "preamp"
                                                  ? (rowDelegate.value / 10 >= 0 ? "+" : "") + (rowDelegate.value / 10).toFixed(1) + " dB"
                                                  : String(Math.round(rowDelegate.value)) + rowDelegate.unitV
                                            color: root.accentColor
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.typeLabel
                                            Layout.preferredWidth: 64
                                        }
                                    }

                                    // stepper
                                    RowLayout {
                                        visible: rowDelegate.rowType === "stepper"
                                        spacing: Theme.spacingXs

                                        HeaderButton {
                                            text: "−"
                                            onClicked: {
                                                var v = rowDelegate.value - rowDelegate.stepV
                                                if (v >= rowDelegate.minV)
                                                    vm.set_value(rowDelegate.rowId, v)
                                            }
                                        }
                                        Label {
                                            text: Number(rowDelegate.value).toFixed(rowDelegate.decimals) + rowDelegate.unitV
                                            color: root.colors["text_primary"]
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.typeLabel
                                            Layout.preferredWidth: 70
                                            horizontalAlignment: Text.AlignHCenter
                                        }
                                        HeaderButton {
                                            text: "+"
                                            onClicked: {
                                                var v = rowDelegate.value + rowDelegate.stepV
                                                if (v <= rowDelegate.maxV)
                                                    vm.set_value(rowDelegate.rowId, v)
                                            }
                                        }
                                    }

                                    // color picker
                                    Row {
                                        visible: rowDelegate.rowType === "color"
                                        spacing: Theme.spacingXs

                                        Repeater {
                                            model: rowDelegate.items

                                            delegate: Rectangle {
                                                required property var modelData
                                                width: 28; height: 28; radius: 14
                                                color: modelData
                                                border.width: 2
                                                border.color: String(rowDelegate.value).toLowerCase() === String(modelData).toLowerCase()
                                                              ? root.colors["text_primary"] : "transparent"
                                                MouseArea {
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: vm.set_value(rowDelegate.rowId, modelData)
                                                }
                                            }
                                        }
                                    }

                                    // botón
                                    HeaderButton {
                                        visible: rowDelegate.rowType === "button"
                                        text: rowDelegate.label
                                        danger: rowDelegate.variant === "danger"
                                        active: rowDelegate.variant === "primary"
                                        onClicked: vm.action(rowDelegate.rowId)
                                    }

                                    // info
                                    Label {
                                        visible: rowDelegate.rowType === "info"
                                        text: String(rowDelegate.value)
                                        color: root.accentColor
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.typeBody
                                        font.weight: Font.Bold
                                    }

                                    // input
                                    TextField {
                                        visible: rowDelegate.rowType === "input"
                                        Layout.preferredWidth: 220
                                        text: String(rowDelegate.value)
                                        echoMode: rowDelegate.password ? TextInput.Password : TextInput.Normal
                                        color: root.colors["text_primary"]
                                        placeholderText: rowDelegate.desc
                                        placeholderTextColor: root.colors["text_secondary"]
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 13
                                        leftPadding: Theme.spacingSm
                                        background: Rectangle {
                                            radius: Theme.radiusSm
                                            color: root.colors["bg_elevated"]
                                            border.width: 1
                                            border.color: parent.activeFocus ? root.accentColor : root.colors["border"]
                                        }
                                        onEditingFinished: vm.set_value(rowDelegate.rowId, text)
                                    }
                                }
                            }

                            // ── EQ bands (10 sliders verticales) ──────
                            Rectangle {
                                visible: rowDelegate.rowType === "eq_bands"
                                Layout.fillWidth: true
                                Layout.preferredHeight: 240
                                radius: Theme.radiusLg
                                color: root.colors["bg_elevated"]
                                border.width: 1
                                border.color: root.accentWithAlpha(0.08)

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: Theme.spacingLg
                                    spacing: Theme.spacingSm

                                    Repeater {
                                        model: vm.eqBands

                                        delegate: ColumnLayout {
                                            id: bandCol
                                            required property int index
                                            required property double modelData

                                            Layout.fillWidth: true
                                            Layout.fillHeight: true
                                            spacing: Theme.spacingXs

                                            // valor
                                            Label {
                                                Layout.fillWidth: true
                                                text: (bandCol.modelData > 0 ? "+" : "") + bandCol.modelData.toFixed(1)
                                                color: bandCol.modelData !== 0 ? root.accentColor : root.colors["text_secondary"]
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.typeCaption
                                                horizontalAlignment: Text.AlignHCenter
                                            }

                                            Slider {
                                                orientation: Qt.Vertical
                                                Layout.fillHeight: true
                                                Layout.alignment: Qt.AlignHCenter
                                                from: -12
                                                to: 12
                                                stepSize: 0.1
                                                value: bandCol.modelData
                                                enabled: vm.eqEnabled
                                                onMoved: vm.set_eq_band(bandCol.index, value)

                                                background: Rectangle {
                                                    x: parent.width / 2 - 2
                                                    width: 4
                                                    height: parent.availableHeight
                                                    radius: 2
                                                    color: root.colors["bg_high"]

                                                    Rectangle {
                                                        y: parent.height / 2
                                                        width: 4
                                                        radius: 2
                                                        height: Math.abs(parent.parent.position - 0.5) * parent.height
                                                        color: root.accentColor
                                                    }
                                                }
                                                handle: Rectangle {
                                                    y: parent.topPadding + parent.visualPosition * (parent.availableHeight - height)
                                                    x: parent.width / 2 - width / 2
                                                    width: 14; height: 14; radius: 7
                                                    color: root.accentColor
                                                }
                                            }

                                            Label {
                                                Layout.fillWidth: true
                                                text: vm.eqBandLabels[bandCol.index] || ""
                                                color: root.colors["text_secondary"]
                                                font.family: Theme.fontFamily
                                                font.pixelSize: Theme.typeCaption
                                                horizontalAlignment: Text.AlignHCenter
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }
        }
    }
}
