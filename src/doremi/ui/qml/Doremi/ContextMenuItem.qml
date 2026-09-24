import QtQuick
import QtQuick.Controls
import Doremi 1.0

MenuItem {
    id: root

    implicitHeight: 40
    leftPadding: Theme.spacingMd
    rightPadding: Theme.spacingMd

    contentItem: Label {
        text: root.text
        color: root.enabled ? themeBridge.colors["text_primary"]
                            : themeBridge.colors["text_secondary"]
        font.family: Theme.fontFamily
        font.pixelSize: Theme.typeBody
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: Theme.radiusSm
        color: root.highlighted ? themeBridge.colors["bg_high"] : "transparent"
    }
}
