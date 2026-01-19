// List Available Output Module Templates and save to file
// After Effects ExtendScript

(function() {
    var outputPath = "C:/claude/ae_nexrender_module/output/output_modules.txt";
    var outputFile = new File(outputPath);
    outputFile.open("w");

    try {
        // 임시 컴포지션 생성
        var tempComp = app.project.items.addComp("_TEMP_COMP_", 1920, 1080, 1, 1, 30);

        // 렌더 큐에 추가
        var rqItem = app.project.renderQueue.items.add(tempComp);
        var om = rqItem.outputModule(1);

        // Output Module 템플릿 목록
        var templates = om.templates;

        outputFile.writeln("=== Available Output Module Templates ===");
        outputFile.writeln("Total: " + templates.length + " templates");
        outputFile.writeln("");

        for (var i = 0; i < templates.length; i++) {
            outputFile.writeln((i + 1) + ". " + templates[i]);
        }

        outputFile.writeln("");
        outputFile.writeln("=== Alpha-related templates ===");
        var alphaTemplates = [];
        for (var i = 0; i < templates.length; i++) {
            var tpl = templates[i].toLowerCase();
            if (tpl.indexOf("alpha") !== -1 ||
                tpl.indexOf("4444") !== -1 ||
                tpl.indexOf("animation") !== -1 ||
                tpl.indexOf("png") !== -1 ||
                tpl.indexOf("tiff") !== -1 ||
                tpl.indexOf("targa") !== -1 ||
                tpl.indexOf("openexr") !== -1) {
                outputFile.writeln("  * " + templates[i]);
                alphaTemplates.push(templates[i]);
            }
        }

        if (alphaTemplates.length === 0) {
            outputFile.writeln("  (No alpha-related templates found)");
        }

        // 정리
        rqItem.remove();
        tempComp.remove();

        outputFile.writeln("");
        outputFile.writeln("=== Done ===");

    } catch (e) {
        outputFile.writeln("Error: " + e.toString());
    }

    outputFile.close();

    // AE 종료
    app.quit();
})();
