// import jasmine from "jasmine";
import report from "jasmine-reporters"
import { influxQueryBuilder } from "../src/grafana";

let junitReporter = new report.JUnitXmlReporter({
    savePath: "./spec/reports",
    filePrefix: "junit-format",
    consolidateAll: true
});
// Add reporter to jasmine
jasmine.getEnv().addReporter(junitReporter);

describe('testing grafana.ts', () => {
    it('influx query builder trafo', () => {
        // inputs
        let oldQuery: string = `from(bucket: "guardian_system_state")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_field"] == "vm_pu")
  |> filter(fn: (r) => r["_measurement"] == "trafo" or r["_measurement"] == "line" or r["_measurement"] == "bus" or r["_measurement"] == "load" or r["_measurement"] == "sgen")
  |> filter(fn: (r) => r["id"] == "0-bus-17" or r["id"] == "0-bus-62")
  |> group(columns: ["id"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")`;
        let cpesComponents: string[] = ["0-trafo-7", "0-trafo-1"];
        let field: string = "loading_percent";

        // expected
        let newQuery: string = `from(bucket: "guardian_system_state")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_field"] == "loading_percent")
  |> filter(fn: (r) => r["id"] == "0-trafo-7" or r["id"] == "0-trafo-1")
  |> group(columns: ["id"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")\n`;

        // test
        let result = influxQueryBuilder(oldQuery, field, cpesComponents);
        expect(result).toEqual(newQuery);
    });
});
