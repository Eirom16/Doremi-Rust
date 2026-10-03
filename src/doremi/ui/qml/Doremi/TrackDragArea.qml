import QtQuick

Item {
    id: root
    property var track: ({})
    Drag.active: handler.active
    Drag.keys: ["doremi-track"]
    Drag.dragType: Drag.Automatic
    Drag.supportedActions: Qt.CopyAction
    Drag.mimeData: ({"application/x-doremi-track": JSON.stringify(track)})
    DragHandler { id: handler; target: null }
}
