import canvas_onmousedown from "./canvas.onmousedown";
import canvas_onmousemove from "./canvas.onmousemove";
import canvas_onmouseup from "./canvas.onmouseup";
import canvas_onwheel from "./canvas.onwheel";
import document_onkeydown from "./document.onkeydown";
import document_onkeyup from "./document.onkeyup";
import openInfoBoardBtn_onclick from "./open-info-board-btn.onclick";
import timelineSlider_oninput from "./timeline-slider.oninput";
import window_resize from "./window.onresize";

export default {
  canvas: {
    onmousedown: canvas_onmousedown,
    onmousemove: canvas_onmousemove,
    onmouseup: canvas_onmouseup,
    onwheel: canvas_onwheel
  },
  document: {
    onkeydown: document_onkeydown,
    onkeyup: document_onkeyup,
  },
  openInfoboardBtn: {
    onclick: openInfoBoardBtn_onclick
  },
  timelineSlider: {
    oninput: timelineSlider_oninput
  },
  window: {
    onresize: window_resize
  }
}
