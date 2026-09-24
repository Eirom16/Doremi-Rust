import QtQuick
import QtQuick.Controls
import Doremi 1.0

Menu {
    id: root

    padding: Theme.spacingXxs

    background: Rectangle {
        implicitWidth: 248
        radius: Theme.radiusMd
        color: themeBridge.colors["bg_elevated"]
        border.width: 1
        border.color: themeBridge.colors["border"]
    }
}
