import QtQuick
import QtQuick.Controls
import Doremi 1.0

Rectangle {
    id: root

    property int borderRadius: Theme.radiusMd
    property color baseColor: root.colors ? root.colors["bg_surface"] : "#1e1e2e"
    property color highlightColor: root.colors ? root.colors["bg_high"] : "#313244"
    property var colors: (typeof themeBridge !== "undefined" && themeBridge && themeBridge.colors)
                         ? themeBridge.colors
                         : null

    radius: borderRadius
    color: baseColor
    clip: true

    Rectangle {
        id: pulse
        anchors.fill: parent
        radius: root.radius
        color: root.highlightColor
        opacity: 0.3

        SequentialAnimation on opacity {
            loops: Animation.Infinite
            running: root.visible

            NumberAnimation {
                from: 0.2
                to: 0.7
                duration: 800
                easing.type: Easing.InOutQuad
            }
            NumberAnimation {
                from: 0.7
                to: 0.2
                duration: 800
                easing.type: Easing.InOutQuad
            }
        }
    }
}
