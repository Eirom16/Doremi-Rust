import QtQuick
import QtQuick.Controls
import Doremi 1.0

ComboBox {
    id: root

    property string label: ""
    property string selectedKey: ""
    property var options: []
    signal choiceSelected(string key)
    readonly property var colors: themeBridge.colors

    implicitWidth: 200
    implicitHeight: 36
    model: options
    textRole: "label"
    valueRole: "key"
    currentIndex: {
        for (let i = 0; i < options.length; ++i) {
            if (options[i].key === selectedKey)
                return i
        }
        return -1
    }
    onActivated: choiceSelected(currentValue)
    Accessible.name: label
    Accessible.description: displayText
    font.family: Theme.fontFamily
    font.pixelSize: Theme.typeLabel
    leftPadding: Theme.spacingSm
    rightPadding: Theme.spacingSm
    palette.text: colors["text_primary"]
    palette.windowText: colors["text_primary"]
    palette.buttonText: colors["text_primary"]
    palette.base: colors["bg_surface"]
    palette.window: colors["bg_elevated"]
    palette.button: colors["bg_surface"]
    palette.highlight: colors["accent"]
    palette.highlightedText: colors["text_on_accent"]

    contentItem: Label {
        text: root.label + " · " + root.displayText
        color: root.colors["text_primary"]
        font: root.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        rightPadding: root.indicator.width + Theme.spacingXs
    }
    indicator: Text {
        x: root.width - width - root.rightPadding
        y: (root.height - height) / 2
        text: "expand_more"
        font.family: "Material Symbols Rounded"
        font.pixelSize: 20
        color: root.colors["text_secondary"]
    }
    background: Rectangle {
        color: root.down || root.hovered ? root.colors["bg_elevated"] : root.colors["bg_surface"]
        radius: Theme.radiusSm
        border.width: 1
        border.color: root.activeFocus || root.popup.visible ? root.colors["accent"] : root.colors["border"]
    }
}
