// Setup Alpha Output Module Template for CyprusDesign.aep
// After Effects ExtendScript
// Run with: AfterFX.exe -r "path/to/this/script.jsx"

#target aftereffects

(function() {
    var logPath = "C:/claude/ae_nexrender_module/output/alpha_setup_log.txt";
    var logFile = new File(logPath);
    logFile.open("w");

    function log(msg) {
        logFile.writeln("[" + new Date().toLocaleString() + "] " + msg);
        $.writeln(msg);
    }

    try {
        log("=== Alpha Output Module Setup ===");

        // 프로젝트 열기
        var projectPath = "C:/claude/automation_ae/templates/CyprusDesign/CyprusDesign.aep";
        var projectFile = new File(projectPath);

        if (!projectFile.exists) {
            log("ERROR: Project file not found: " + projectPath);
            logFile.close();
            return;
        }

        log("Opening project: " + projectPath);
        app.open(projectFile);
        log("Project opened successfully");

        // 임시 컴포지션 생성
        log("Creating temp composition...");
        var tempComp = app.project.items.addComp("_ALPHA_SETUP_TEMP_", 1920, 1080, 1, 1, 30);

        // 렌더 큐에 추가
        var rqItem = app.project.renderQueue.items.add(tempComp);
        var om = rqItem.outputModule(1);

        // 현재 템플릿 목록 확인
        var templates = om.templates;
        log("Available templates: " + templates.length);

        // 알파 채널 지원 템플릿 검색
        var alphaTemplate = null;
        var templateList = [];

        for (var i = 0; i < templates.length; i++) {
            templateList.push(templates[i]);
            var tpl = templates[i].toLowerCase();
            if (tpl.indexOf("alpha") !== -1 ||
                tpl.indexOf("4444") !== -1 ||
                tpl.indexOf("animation") !== -1) {
                alphaTemplate = templates[i];
                log("Found alpha template: " + templates[i]);
            }
        }

        log("");
        log("All templates:");
        for (var i = 0; i < templateList.length; i++) {
            log("  " + (i+1) + ". " + templateList[i]);
        }

        // 알파 템플릿이 없으면 Lossless를 기반으로 설정
        if (!alphaTemplate) {
            log("");
            log("No alpha template found. Trying to configure Lossless...");

            // Lossless 템플릿 적용
            try {
                om.applyTemplate("Lossless");
                log("Applied Lossless template");

                // 템플릿을 "Lossless with Alpha"로 저장 시도
                // (AE에서 Output Module 설정을 스크립트로 완전히 제어하기 어려움)
                log("Note: To enable alpha, manually set Output Module:");
                log("  1. Open After Effects");
                log("  2. Go to Edit > Templates > Output Module");
                log("  3. Create new template 'Alpha MOV' with:");
                log("     - Format: QuickTime");
                log("     - Video Codec: Animation");
                log("     - Channels: RGB + Alpha");

            } catch (e) {
                log("Error applying Lossless: " + e.toString());
            }
        } else {
            log("");
            log("Using existing alpha template: " + alphaTemplate);
        }

        // 정리
        log("");
        log("Cleaning up...");
        rqItem.remove();
        tempComp.remove();

        // 프로젝트 저장 (변경사항이 있는 경우)
        // app.project.save();
        log("Done. Project not saved (no changes needed).");

        log("");
        log("=== Setup Complete ===");

    } catch (e) {
        log("ERROR: " + e.toString());
    }

    logFile.close();

    // 10초 후 종료
    $.sleep(5000);
    app.quit();
})();
