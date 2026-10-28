<p align="center">
  <img src="logo.jpeg" alt="DeGAS logo" width="160">
</p>

# pydegas

Gradient-based optimization of probabilistic programs without sampling, based
on DeGAS ([https://doi.org/10.1007/978-3-032-22752-2_29](https://doi.org/10.1007/978-3-032-22752-2_29)).

| Project | What it is |
|---|---|
| [pydegas](libs/pydegas/docs/index.md) | Python library |
| [degas-api](libs/degas-api/docs/index.md) | FastAPI service running optimizations over a WebSocket |
| [degas-ui](libs/degas-ui/docs/index.md) | web interface for the service |


---

- Use the library: [getting started](libs/pydegas/docs/getting-started.md)
- Run the web application locally: [local stack](docs/local-stack.md)
- Work on the code: [contributing](CONTRIBUTING.md)

## License

MIT; see [LICENSE](LICENSE). pydegas is a reimplementation of the DeGAS
reference code at [frarandone/DeGAS](https://github.com/frarandone/DeGAS).

## Citation

```bibtex
@inproceedings{randone2026degas,
  title={DeGAS: Gradient-Based Optimization of Probabilistic Programs without Sampling},
  author={Randone, Francesca and Doz, Romina and Tribastone, Mirco and Bortolussi, Luca},
  booktitle={International Conference on Tools and Algorithms for the Construction and Analysis of Systems},
  pages={566--585},
  year={2026},
  organization={Springer}
}
```
