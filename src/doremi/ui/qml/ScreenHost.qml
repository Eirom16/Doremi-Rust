import QtQuick

Item {
    id: root

    // Source and VM must be delivered as one operation. Updating two bound
    // properties independently briefly gives the old screen the new VM (or
    // vice versa), which is particularly destructive for QML routes.
    function showScreen(source, vm) {
        if (!source || !vm) {
            screenLoader.source = ""
            return
        }
        if (screenLoader.item && screenLoader.source === source) {
            screenLoader.item.screenVm = vm
            return
        }
        screenLoader.setSource(source, { "screenVm": vm })
    }

    Loader {
        id: screenLoader
        objectName: "screenLoader"
        anchors.fill: parent
        onLoaded: {
            if (item) {
                item.opacity = 0
                fadeIn.target = item
                fadeIn.start()
            }
        }
    }

    NumberAnimation {
        id: fadeIn
        property: "opacity"
        from: 0
        to: 1
        duration: 180
        easing.type: Easing.OutCubic
    }
}
