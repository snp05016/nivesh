import XCTest
@testable import stockme

/// IOSUI-19: a sliver holding must draw a sliver, never a near-full ring.
@MainActor
final class DonutGeometryTests: XCTestCase {

    func testSmallHoldingDoesNotWrap() {
        let segs = DonutGeometry.segments(values: [0.7, 0.298, 0.002])
        XCTAssertEqual(segs.count, 3)
        for s in segs { XCTAssertGreaterThan(s.end, s.start) }
        XCTAssertEqual(segs.map(\.index), [0, 1, 2])
        XCTAssertTrue(zip(segs, segs.dropFirst()).allSatisfy { $0.start < $1.start })
        XCTAssertLessThanOrEqual(segs.last!.end, 270)
        // The 0.2% slice spans well under 1 degree.
        XCTAssertLessThan(segs[2].end - segs[2].start, 1)
    }

    func testZeroValuesAreSkipped() {
        let one = DonutGeometry.segments(values: [1, 0])
        XCTAssertEqual(one.count, 1)
        XCTAssertEqual(one[0].index, 0)
        XCTAssertTrue(DonutGeometry.segments(values: [0, 0]).isEmpty)
        XCTAssertTrue(DonutGeometry.segments(values: []).isEmpty)
    }

    func testTinySliceIsSliver() {
        let segs = DonutGeometry.segments(values: [1, 0.0001])
        XCTAssertEqual(segs.count, 2)
        XCTAssertGreaterThan(segs[1].end, segs[1].start)
        XCTAssertLessThan(segs[1].end - segs[1].start, 1)
    }
}
