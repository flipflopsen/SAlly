import State from "../state";

export default function exitEditMode(state: State){
    state.editMode = false;
    console.log("exiting EDITMODE");
    state.dragsElement = false;
    // activate timelineslider again
    state.timelineSlider.disabled = false;
    state.timelineDiv.hidden = false;
    // re-activate buttons
    state.openInfoboardBtn.hidden = false;
    state.backBtn.hidden = false;

    // undo markings
    let dicts = [state.busDict, state.extGridDict, state.switchDict];
    dicts.forEach((dict) => {
      for (const [key, obj] of Object.entries(dict)) {
        obj.editModeBorderMarker2 = false;
        obj.editModeBorderMarker1 = false;
      }
    });
}
