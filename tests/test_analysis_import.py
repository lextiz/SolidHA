def test_analysis_reexports() -> None:
    import agent.analysis as analysis
    from agent.problems import ProblemLogger, monitor

    assert analysis.ProblemLogger is ProblemLogger
    assert analysis.monitor is monitor

