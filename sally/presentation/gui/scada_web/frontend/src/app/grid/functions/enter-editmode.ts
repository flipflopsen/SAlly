import State from "../state";

export default function enterEditMode(state: State){
    state.editMode = true;
    console.log("entering EDITMODE");
    // deactivate and hide timelineslider
    state.timelineSlider.disabled = true;
    state.timelineDiv.hidden = true;
    // deactivate buttons
    state.openInfoboardBtn.hidden = true;
    state.backBtn.hidden = true;

    let dicts = [state.busDict, state.extGridDict, state.switchDict];
    dicts.forEach((dict) => {
      for (const [key, obj] of Object.entries(dict)) {
        // mark all root nodes
        if (!obj.hasParent) obj.editModeBorderMarker2 = true;
        // mark all nodes with too many children. Make it visible that they are
        // overburdend in a graphical way
        if (obj.children.length > 2) obj.editModeBorderMarker1 = true;
      }
    });
}
