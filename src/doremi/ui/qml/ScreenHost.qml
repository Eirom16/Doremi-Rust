import QtQuick

Item {
    id: root

    property url screenSource: ""
    property var screenVm: null

    function applyViewModel() {
        if (screenLoader.item && "screenVm" in screenLoader.item)
            screenLoader.item.screenVm = root.screenVm
    }

    onScreenVmChanged: applyViewModel()

    Loader {
        id: screenLoader
        objectName: "screenLoader"
        anchors.fill: parent
        source: root.screenSource
        onLoaded: {
            root.applyViewModel()
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
