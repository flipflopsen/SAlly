import { DOCUMENT } from "@angular/common";

import {
  inject,
  ViewChild,
  Component,
  AfterViewInit,
  HostListener,
  ElementRef,
  OnInit,
} from "@angular/core";
import { RouterLink } from "@angular/router";

import Vector2D from "./classes/vector-2d";
import State from "./state";
import Cable from "./classes/cable";
import ExtGrid from "./classes/ext-grid";
import Bus from "./classes/bus";
import Trafo from "./classes/trafo";
import Load from "./classes/load";
import Generator from "./classes/generator";
import init from "./functions/init";
import EVENT_HANDLER from "./events";

import * as SETTINGS from "./settings";
import { LayoutService } from "./layout.service";
import { GrafanaControlComponent } from "../dashboard/grafana-control/grafana-control.component"
import { GrafanaService } from "../dashboard/grafana.service"
import { DataService } from "../dashboard/data.service";


@Component({
  selector: 'app-grid',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './grid.component.html',
  styleUrl: './grid.component.scss'
})
export class GridComponent implements AfterViewInit {
  @ViewChild("backBtn")
  backBtn!: ElementRef<HTMLButtonElement>;

  @ViewChild("openInfoBoardBtn")
  openInfoBoardBtn!: ElementRef<HTMLButtonElement>;

  @ViewChild("canvasDiv")
  canvasDiv!: ElementRef<HTMLDivElement>;

  @ViewChild("mainCanvas")
  canvas!: ElementRef<HTMLCanvasElement>;

  @ViewChild("timelineDiv")
  timelineDiv!: ElementRef<HTMLDivElement>;

  @ViewChild("timelineSlider")
  timelineSlider!: ElementRef<HTMLInputElement>;

  @ViewChild("selectedRecordText")
  selectedRecordText!: ElementRef<HTMLOutputElement>;

  document = inject(DOCUMENT);
  // window = inject(Window);

  EVENT_HANDLER = EVENT_HANDLER;

  state!: State;

  constructor(
    private layoutService: LayoutService,
    private grafanaService: GrafanaService,
    private dataService: DataService
  ) { }

  ngAfterViewInit() {
    this.openInfoBoardBtn.nativeElement.innerHTML = "Please select an element";

    let bufferCanvas = this.document.createElement("canvas");
    let scaleWindowWidth = SETTINGS.MIN_ZOOM;
    let scaleWindowHeight = SETTINGS.MIN_ZOOM;

    let cablesArray: Cable[] = [];
    let busDict: Record<string, Bus> = {};
    let extGridDict: Record<string, ExtGrid> = {};
    let trafoDict: Record<string, Trafo> = {};
    let loadDict: Record<string, Load> = {};
    let generatorsDict: Record<string, Generator> = {};
    let lineDict: Record<string, Cable> = {};
    let switchDict: Record<string, Bus> = {};

    this.state = {
      grafanaControl: new GrafanaControlComponent(this.grafanaService),
      canvas: this.canvas.nativeElement,
      timelineDiv: this.timelineDiv.nativeElement,
      backBtn: this.backBtn.nativeElement,
      openInfoboardBtn: this.openInfoBoardBtn.nativeElement,
      timelineSlider: this.timelineSlider.nativeElement,
      selectedRecordText: this.selectedRecordText.nativeElement,

      trafoImg: this.createImgElement(SETTINGS.trafo_img_src),
      loadImg: this.createImgElement(SETTINGS.load_img_src),
      generatorImg: this.createImgElement(SETTINGS.generator_img_src),
      extGridImg: this.createImgElement(SETTINGS.ext_grid_img_src),
      busImg: this.createImgElement(SETTINGS.bus_img_src),
      switchImg: this.createImgElement(SETTINGS.switch_img_src),

      overvoltageImg: this.createImgElement(SETTINGS.overvoltage_img_src),
      undervoltageImg: this.createImgElement(SETTINGS.undervoltage_img_src),

      OVERALLWIDTH: window.innerWidth,
      OVERALLHEIGHT: window.innerHeight - this.timelineDiv.nativeElement.clientHeight,

      bufferCanvas,

      context: this.canvas.nativeElement.getContext("2d")!,
      bufferContext: bufferCanvas.getContext("2d")!,

      editMode: false,
      animationId: 0,
      userChange: true,
      scalingChange: true,
      valueChange: true,

      electricComponentsArray: [],
      cablesArray,
      clickedElementsArray: [],
      hoverElementsArray: [],
      clickedElement: null,

      mouseDown: false,
      lastDraggingCoor: new Vector2D(0, 0),
      mousePos: new Vector2D(0, 0),
      translatedMousePos: new Vector2D(0, 0),
      dragsElement: false,
      keyE: false,
      keyS: false,
      saveGridEvent: false,

      marginTop: 0,
      marginLeft: 0,
      scaleWindowHeight,
      scaleWindowWidth,
      //scaleFactor: scaleWindowHeight * (this.canvas.nativeElement.height / bufferCanvas.height),
      scaleFactor: 1, // gets overwritten in init anyway
      defaultScaleFactor: 1, // gets overwritten in init anyway

      clickedBtn: false,
      lastClickedElement: null,

      tryToAddChildLaterList: [],
      networkConfigFile: null,

      myDbase: null,
      busDict,
      extGridDict,
      trafoDict,
      loadDict,
      generatorsDict,
      lineDict,
      switchDict,
      currentFrame: 0,

      elemTypeToArrayDict: {
        line: lineDict,
        bus: busDict,
        ext_grid: extGridDict,
        trafo: trafoDict,
        load: loadDict,
        sgen: generatorsDict,
      },

      unitToAttributeDict: {
        vm_pu: "voltage_pu",
        va_degree: "voltageToCurrentAngle",
        p_mw: "activePower_mw",
        q_mvar: "reactivePower_var",
        in_service: "switchInService",
        loading_percent: "loading_percent",
        closed: "switchClosed",
      }
    }

    // the following are just initialization values, changes during scaling
    this.canvas.nativeElement.width = this.state.OVERALLWIDTH;
    this.canvas.nativeElement.height = this.state.OVERALLHEIGHT;
    this.state.bufferCanvas.width = this.canvas.nativeElement.width * SETTINGS.MAX_ZOOM;
    this.state.bufferCanvas.height = this.canvas.nativeElement.height * SETTINGS.MAX_ZOOM;

    // FIXME: this is async, why?
    init(this.state, this.layoutService);

    // Subscribe to topology updates from Sally bridge
    this.dataService.topology().subscribe({
      next: (topology) => {
        console.log("[GridComponent] Received topology from Sally:", topology);
        // TODO: Process topology and update state if needed
        // The init function already handles topology loading from the backend
      },
      error: (error) => {
        console.error("[GridComponent] Error receiving topology:", error);
      }
    });

    // Subscribe to real-time sensor data updates
    this.dataService.step().subscribe({
      next: ([timestamp, sensorData]) => {
        // Update grid visualization with new sensor data
        this.updateGridWithSensorData(timestamp, sensorData);
      },
      error: (error) => {
        console.error("[GridComponent] Error receiving sensor data:", error);
      }
    });
  }

  /**
   * Update the grid visualization with new sensor data from Sally
   */
  private updateGridWithSensorData(timestamp: number, sensorData: any): void {
    // Update bus voltages
    if (sensorData.bus && this.state.busDict) {
      Object.entries(sensorData.bus).forEach(([busId, busData]: [string, any]) => {
        const bus = this.state.busDict[busId];
        if (bus && busData.vm_pu !== undefined) {
          bus.voltage_pu = busData.vm_pu;
        }
      });
    }

    // Update line loading
    if (sensorData.line && this.state.lineDict) {
      Object.entries(sensorData.line).forEach(([lineId, lineData]: [string, any]) => {
        const line = this.state.lineDict[lineId];
        if (line && lineData.loading_percent !== undefined) {
          line.loading_percent = lineData.loading_percent;
        }
      });
    }

    // Update load power
    if (sensorData.load && this.state.loadDict) {
      Object.entries(sensorData.load).forEach(([loadId, loadData]: [string, any]) => {
        const load = this.state.loadDict[loadId];
        if (load) {
          if (loadData.p_mw !== undefined) load.activePower_mw = loadData.p_mw;
          if (loadData.q_mvar !== undefined) load.reactivePower_var = loadData.q_mvar;
        }
      });
    }

    // Update generator power
    if (sensorData.sgen && this.state.generatorsDict) {
      Object.entries(sensorData.sgen).forEach(([genId, genData]: [string, any]) => {
        const gen = this.state.generatorsDict[genId];
        if (gen) {
          if (genData.p_mw !== undefined) gen.activePower_mw = genData.p_mw;
          if (genData.q_mvar !== undefined) gen.reactivePower_var = genData.q_mvar;
        }
      });
    }

    // Update trafo loading
    if (sensorData.trafo && this.state.trafoDict) {
      Object.entries(sensorData.trafo).forEach(([trafoId, trafoData]: [string, any]) => {
        const trafo = this.state.trafoDict[trafoId];
        if (trafo && trafoData.loading_percent !== undefined) {
          trafo.loading_percent = trafoData.loading_percent;
        }
      });
    }

    // Mark that values changed to trigger re-render
    this.state.valueChange = true;
  }

  @HostListener("window:resize", ["$event"])
  onWindowResize(event: Event) {
    this.EVENT_HANDLER.window.onresize(this.state, event);
  }

  @HostListener("document:keydown", ["$event"])
  onDocumentKeydown(event: KeyboardEvent) {
    this.EVENT_HANDLER.document.onkeydown(this.state, event);
  }

  @HostListener("document:keyup", ["$event"])
  onDocumentKeyup(event: KeyboardEvent) {
    this.EVENT_HANDLER.document.onkeyup(this.state, event);
  }

  private createImgElement(src: string) {
    let img = this.document.createElement("img");
    img.src = src;
    return img;
  }
}
