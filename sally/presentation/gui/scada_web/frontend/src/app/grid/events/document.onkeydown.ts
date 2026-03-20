import State from "../state";

export default function onKeyDown(state: State, evt: KeyboardEvent) {
  if(evt.key == "s"){
    state.keyS = true;
  }
  if(evt.key == "e"){
    state.keyE = true;
  }
}
